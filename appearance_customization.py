"""An allowlist of cosmetic preferences; no layout, commands or core labels."""
import re

DEFAULTS={
 'light':{'accent':'#0f6cbd','surface':'#ffffff','control':'#f5f7fa','list':'#ffffff','ink':'#202a3d','muted':'#58657a'},
 'dark':{'accent':'#0f6cbd','surface':'#292b30','control':'#222429','list':'#292b30','ink':'#f3f4f6','muted':'#b7bfcc'},
}
ICONS=('ic_fluent_checkmark_circle_20_regular','ic_fluent_sparkle_20_regular','ic_fluent_leaf_one_20_regular','ic_fluent_book_open_20_regular')

def contrast(a,b):
 def luminance(value):
  rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
  linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
  return sum(x*w for x,w in zip(linear,(.2126,.7152,.0722)))
 x,y=sorted((luminance(a),luminance(b)));return (y+.05)/(x+.05)

def validate(value):
 if not isinstance(value,dict) or set(value)-{'enabled','light','dark','workspaceName','workspaceIcon'}:raise ValueError('只能修改配色和工作区装饰，不能修改布局或核心设置。')
 result={'enabled':bool(value.get('enabled',False)),'workspaceName':str(value.get('workspaceName','')).strip(),'workspaceIcon':value.get('workspaceIcon',ICONS[0])}
 if len(result['workspaceName'])>24 or any(ord(c)<32 for c in result['workspaceName']):raise ValueError('工作区名称最多 24 字，不能包含控制字符。')
 if result['workspaceIcon'] not in ICONS:raise ValueError('请使用提供的工作区图标。')
 for mode,defaults in DEFAULTS.items():
  colors=value.get(mode,{})
  if not isinstance(colors,dict) or set(colors)-set(defaults):raise ValueError('配色字段无效。')
  colors={**defaults,**colors}
  if any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in colors.values()):raise ValueError('颜色必须是 #RRGGBB 格式，不支持透明文字。')
  for foreground in ('ink','muted'):
   for background in ('surface','control','list'):
    if contrast(colors[foreground],colors[background])<4.5:raise ValueError(f'{mode} 配色中文字与背景对比不足，请加深文字或调整背景。')
  # Native controls retain system text colors and white accent-button text.
  for background in ('surface','control','list'):
   if contrast(defaults['ink'],colors[background])<4.5 or contrast(defaults['muted'],colors[background])<4.5:raise ValueError('请保持背景与系统控件文字之间的对比度。')
  if contrast('#ffffff',colors['accent'])<4.5:raise ValueError('主色过浅，按钮白色文字会难以阅读。')
  result[mode]={k:c.lower() for k,c in colors.items()}
 return result
