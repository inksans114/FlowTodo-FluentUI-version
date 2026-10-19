"""Launch a narrow Windows helper on the next start, retaining rollback files."""
import json,os,subprocess,sys
from pathlib import Path
from update_files import destination,file_hash,safe_relative

SCRIPT=r'''param([int]$OldPid,[string]$Stage,[string]$Pending,[string]$Executable)
$ErrorActionPreference='Stop'
$plan=Get-Content -LiteralPath (Join-Path $Stage 'plan.json') -Raw | ConvertFrom-Json
$root=[IO.Path]::GetFullPath($plan.install_root).TrimEnd('\')
$stageRoot=[IO.Path]::GetFullPath((Join-Path $Stage 'files')).TrimEnd('\')
$backupRoot=Join-Path $Stage 'rollback'
$done=@()
function CheckedPath([string]$base,[string]$relative){
 $candidate=[IO.Path]::GetFullPath((Join-Path $base $relative))
 if(-not $candidate.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw '文件路径越界'}
 $parent=Split-Path -Parent $candidate
 while($parent -and $parent.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)){
  if(Test-Path -LiteralPath $parent){if((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '路径包含重解析点'}}
  if($parent -eq $base){break};$parent=Split-Path -Parent $parent
 }
 if(Test-Path -LiteralPath $candidate){if((Get-Item -LiteralPath $candidate -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '文件包含重解析点'}}
 return $candidate
}
try{
 $deadline=(Get-Date).AddSeconds(120)
 while(Get-Process -Id $OldPid -ErrorAction SilentlyContinue){if((Get-Date) -gt $deadline){throw '等待程序退出超时'};Start-Sleep -Milliseconds 300}
 foreach($item in $plan.files){
  $source=CheckedPath $stageRoot $item.path;$target=CheckedPath $root $item.path
  if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() -ne $item.sha256){throw '更新文件校验失败'}
  $backup=CheckedPath $backupRoot $item.path;$existed=Test-Path -LiteralPath $target
  if($existed){New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null;Copy-Item -LiteralPath $target -Destination $backup -Force}
  $done+=@{target=$target;backup=$backup;existed=$existed}
  New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
  $copied=$false
  for($attempt=0;$attempt -lt 8;$attempt++){try{Copy-Item -LiteralPath $source -Destination $target -Force;$copied=$true;break}catch{Start-Sleep -Milliseconds 500}}
  if(-not $copied){throw '更新文件被占用或程序目录不可写'}
  if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $item.sha256){throw '安装后校验失败'}
 }
 Move-Item -LiteralPath $Pending -Destination (Join-Path $Stage 'installed.json') -Force
 @{ok=$true;version=$plan.version}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Stage 'result.json') -Encoding UTF8
}catch{
 $failure=$_.Exception.Message
 for($i=$done.Count-1;$i -ge 0;$i--){$entry=$done[$i];try{if($entry.existed){Copy-Item -LiteralPath $entry.backup -Destination $entry.target -Force}else{Remove-Item -LiteralPath $entry.target -Force}}catch{$failure+='; 回滚失败: '+$_.Exception.Message}}
 if(Test-Path -LiteralPath $Pending){Move-Item -LiteralPath $Pending -Destination (Join-Path $Stage 'failed.json') -Force}
 @{ok=$false;error=$failure}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Stage 'result.json') -Encoding UTF8
}
Start-Process -FilePath $Executable -WorkingDirectory $root -WindowStyle Hidden
'''

def launch_pending(pending_file,current_version,is_newer):
 pending=Path(pending_file)
 if not pending.is_file():return False
 value=json.loads(pending.read_text(encoding='utf-8'));stage=Path(value['stage']).resolve();exe=Path(sys.executable).resolve()
 cache=pending.parent.resolve()
 if not stage.is_relative_to(cache):raise ValueError('待安装文件不属于更新缓存。')
 plan=json.loads((stage/'plan.json').read_text(encoding='utf-8'))
 if plan.get('format')!='flowtodo-staged-v1' or plan.get('version')!=value.get('version') or Path(plan['install_root']).resolve()!=exe.parent:raise ValueError('更新目标与当前软件不一致。')
 if not is_newer(plan['version'],current_version):pending.replace(cache/'ignored-pending.json');return False
 for item in plan['files']:
  source=destination(stage/'files',safe_relative(item['path']));destination(exe.parent,item['path'])
  if source.stat().st_size!=item['size'] or file_hash(source)!=item['sha256']:raise ValueError('下载文件已变化，停止安装。')
 script=cache/'apply-update.ps1';script.write_text(SCRIPT,encoding='utf-8-sig')
 flags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'DETACHED_PROCESS',0)
 subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-OldPid',str(os.getpid()),'-Stage',str(stage),'-Pending',str(pending),'-Executable',str(exe)],creationflags=flags,close_fds=True)
 return True
