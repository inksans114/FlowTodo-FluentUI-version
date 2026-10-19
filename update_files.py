"""Bounded, verified differential updates. Only allowlisted application files."""
import gzip,hashlib,json,os,re,urllib.parse,urllib.request,zipfile
from pathlib import Path,PurePosixPath

MAX_FILE=512*1024*1024
MAX_TOTAL=1500*1024*1024
PROTECTED={'.git','.agents','.codex','data','user_data','userdata','config','settings','updates','work','logs','backups'}

def file_hash(path):
 digest=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(256*1024),b''):digest.update(chunk)
 return digest.hexdigest()

def safe_relative(value):
 if not isinstance(value,str) or not value or '\\' in value or ':' in value:raise ValueError('更新文件路径无效。')
 path=PurePosixPath(value)
 if path.is_absolute() or any(p in ('','.','..') or p.endswith((' ','.')) for p in value.split('/')):raise ValueError('更新文件路径越界。')
 if any(p.lower() in PROTECTED or p.lower().startswith('.env') for p in path.parts) or path.suffix.lower() in ('.vault','.sqlite','.db','.log'):raise ValueError('更新不能覆盖用户数据、密钥或设置。')
 if any(re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',p,re.I) for p in path.parts):raise ValueError('更新文件名无效。')
 return path.as_posix()

def destination(root,relative):
 root=Path(root).resolve();target=root/safe_relative(relative)
 if not target.resolve().is_relative_to(root):raise ValueError('更新不能经过链接写到程序目录以外。')
 current=target
 while current!=root:
  if current.is_symlink() or current.is_junction():raise ValueError('更新路径不能包含链接。')
  current=current.parent
 return target

def trusted_url(url,source):
 parsed=urllib.parse.urlsplit(url);origin=urllib.parse.urlsplit(source)
 if parsed.scheme!='https' or parsed.username or parsed.password or parsed.fragment:raise ValueError('更新来源需要有效 HTTPS 地址。')
 if origin.hostname=='github.com':
  prefix='/inksans114/FlowTodo-FluentUI-version/releases/download/'
  if parsed.netloc!='github.com' or not parsed.path.startswith(prefix):raise ValueError('更新下载地址不属于软件官方仓库。')
 elif parsed.netloc!=origin.netloc or not parsed.path.startswith(origin.path.rsplit('/',1)[0]+'/'):
  raise ValueError('更新文件必须来自配置的服务器发布目录。')
 return url

def read_manifest(raw,source):
 if len(raw)>4*1024*1024:raise ValueError('更新清单过大。')
 value=json.loads(raw)
 if not isinstance(value,dict) or value.get('format')!='flowtodo-update-v1' or not re.fullmatch(r'\d+(?:\.\d+){1,3}',str(value.get('version',''))):raise ValueError('更新清单格式或版本无效。')
 files=value.get('files');names=set();total=0
 if not isinstance(files,list) or not files or len(files)>15000:raise ValueError('更新清单缺少应用文件。')
 for item in files:
  name=safe_relative(item.get('path'));lower=name.casefold()
  if lower in names:raise ValueError('清单包含重复文件。')
  names.add(lower)
  if not isinstance(item.get('size'),int) or not 0<=item['size']<=MAX_FILE or not re.fullmatch('[a-f0-9]{64}',str(item.get('sha256',''))):raise ValueError('清单文件大小或校验值无效。')
  item['url']=trusted_url(urllib.parse.urljoin(source,item['url']),source)
  if item.get('compression') not in ('gzip',None):raise ValueError('文件压缩格式不受支持。')
  total+=item['size']
 if total>MAX_TOTAL or 'flowtodo.exe' not in names:raise ValueError('更新不完整或超过空间限制。')
 value['source']=source;return value

def changed_files(manifest,install_root):
 changed=[]
 for item in manifest['files']:
  target=destination(install_root,item['path'])
  if not target.is_file() or target.stat().st_size!=item['size'] or file_hash(target)!=item['sha256']:changed.append(item)
 return changed

def stage_manifest(manifest,install_root,stage_root,progress=lambda value:None,opener=urllib.request.urlopen):
 stage=Path(stage_root);stage.mkdir(parents=True,exist_ok=True);changes=changed_files(manifest,install_root)
 for index,item in enumerate(changes):
  target=destination(stage/'files',item['path']);target.parent.mkdir(parents=True,exist_ok=True)
  if target.is_file() and target.stat().st_size==item['size'] and file_hash(target)==item['sha256']:continue
  request=urllib.request.Request(item['url'],headers={'User-Agent':'FlowTodo-Updater','Accept':'application/octet-stream'})
  temp=target.with_name(target.name+'.part');total=0
  try:
   with opener(request,timeout=30) as response:
    stream=gzip.GzipFile(fileobj=response) if item.get('compression')=='gzip' else response
    with temp.open('wb') as output:
     while True:
      chunk=stream.read(256*1024)
      if not chunk:break
      total+=len(chunk)
      if total>item['size']:raise ValueError('更新文件大小异常。')
      output.write(chunk)
   if total!=item['size'] or file_hash(temp)!=item['sha256']:raise ValueError('更新文件校验失败，未应用。')
   os.replace(temp,target)
  finally:temp.unlink(missing_ok=True)
  progress(int((index+1)*100/max(1,len(changes))))
 plan={'format':'flowtodo-staged-v1','version':manifest['version'],'install_root':str(Path(install_root).resolve()),'files':changes}
 (stage/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8');progress(100);return plan

def stage_archive(archive_path,version,install_root,stage_root):
 """A full ZIP fallback still replaces only files whose hashes differ."""
 with zipfile.ZipFile(archive_path) as archive:
  entries=[item for item in archive.infolist() if not item.is_dir()]
  if not entries:raise ValueError('更新包为空。')
  parts=[PurePosixPath(i.filename) for i in entries]
  prefix=parts[0].parts[0] if all(len(p.parts)>1 and p.parts[0]==parts[0].parts[0] for p in parts) else ''
  total=0;seen=set();changed=[];stage=Path(stage_root)
  for item in entries:
   if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('更新包不能包含符号链接。')
   name=safe_relative(item.filename[len(prefix)+1:] if prefix else item.filename)
   if name.casefold() in seen:raise ValueError('更新包中有重复文件。')
   seen.add(name.casefold());total+=item.file_size
   if item.file_size>MAX_FILE or total>MAX_TOTAL:raise ValueError('更新包解压体积异常。')
   target=destination(stage/'files',name);target.parent.mkdir(parents=True,exist_ok=True)
   digest=hashlib.sha256();received=0
   with archive.open(item) as stream,target.open('wb') as output:
    for chunk in iter(lambda:stream.read(256*1024),b''):received+=len(chunk);digest.update(chunk);output.write(chunk)
   if received!=item.file_size:raise ValueError('更新包文件不完整。')
   original=destination(install_root,name)
   if original.is_file() and file_hash(original)==digest.hexdigest():target.unlink();continue
   changed.append({'path':name,'size':received,'sha256':digest.hexdigest()})
  if 'flowtodo.exe' not in seen:raise ValueError('更新包缺少 FlowTodo.exe。')
 plan={'format':'flowtodo-staged-v1','version':version,'install_root':str(Path(install_root).resolve()),'files':changed}
 stage.mkdir(parents=True,exist_ok=True);(stage/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8');return plan
