#!/usr/bin/env python3
"""Extract authored atlas regions and build the versioned browser rig (D-059).

This crops generated runtime tiles; it does not paint replacement artwork.
Coordinates and limits are configuration targets, not anatomical measurements.
"""
import json
import argparse
import shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'frontend/public/assets/teacher-mesh'
# Explicit authored regions: the image generator did not preserve equal grid cells.
REGIONS={
 'body-atlas-v1.png':{
  'body':(60,0,500,512),'back-hair':(550,0,960,530),
  'right-arm':(120,525,360,1040),'left-arm':(665,525,915,1045),
  'open-hand':(45,1145,460,1450),'relaxed-hand':(655,1060,905,1530)},
 'face-atlas-v1.png':{
  'face':(50,45,365,580),'front-hair':(410,45,830,610),'glasses':(840,245,1220,375),
  'eyes':(20,715,400,835),'brows':(430,710,800,795),'lids':(845,735,1220,840),
  'mouth-neutral':(65,980,355,1210),'mouth-a':(470,960,765,1230),'mouth-o':(915,970,1150,1220)},
 'hands-atlas-v1.png':{'point-hand':(0,0,887,887),'wave-hand':(887,0,1774,887)}}

REGIONS_V2={
 'body-atlas-v2.png':{
  'body':(35,0,565,645),'back-hair':(615,0,1000,670),
  'right-arm':(135,650,400,1145),'left-arm':(625,650,900,1145),
  'open-hand':(65,1180,480,1455),'relaxed-hand':(660,1150,860,1536)},
 'face-atlas-v2.png':{
  'face':(20,25,425,610),'front-hair':(420,25,835,610),'glasses':(840,235,1230,385),
  'eyes':(20,740,415,865),'brows':(440,750,800,835),'lids':(840,745,1220,865),
  'mouth-neutral':(70,985,380,1215),'mouth-a':(470,975,780,1235),'mouth-o':(910,975,1150,1225)},
 'hands-atlas-v1.png':{'point-hand':(0,0,887,887),'wave-hand':(887,0,1774,887)}}

REGIONS_V3={
 'body-atlas-v3.png':{
  'body':(65,0,610,700),'back-hair':(615,0,1024,705),
  },
 'arms-atlas-v3.png':{
  'right-arm':(130,10,430,1030),'left-arm':(600,10,900,1030),
  'open-hand':(565,1080,1024,1536),'relaxed-hand':(45,1060,510,1536)},
 'face-atlas-v3.png':{
  'face':(20,70,425,695),'front-hair':(400,35,845,680),
  'glasses':(840,295,1230,435),
  'eyes':(30,775,410,900),'brows':(440,800,805,865),'lids':(840,775,1220,905),
  'mouth-neutral':(85,1005,355,1215),'mouth-a':(480,1000,760,1220),
  'mouth-o':(915,1000,1140,1220)},
 'hands-atlas-v1.png':{'point-hand':(0,0,887,887),'wave-hand':(887,0,1774,887)}}


def build(revision=7):
 if revision==7:
  from build_teacher_mesh_v7 import build as build_v7
  return build_v7()
 if revision==6:
  from build_teacher_mesh_v6 import build as build_v6
  return build_v6()
 if revision==5:
  from build_teacher_mesh_v5 import build as build_v5
  return build_v5()
 if revision==4:
  from build_teacher_mesh_v4 import build as build_v4
  return build_v4()
 out={}
 for source,regions in ({1:REGIONS,2:REGIONS_V2,3:REGIONS_V3}[revision]).items():
  with Image.open(OUT/'source'/source) as atlas:
   for name,region in regions.items():
    part=atlas.crop(region).convert('RGBA')
    bounds=part.getchannel('A').point(lambda a:255 if a>30 else 0).getbbox()
    if bounds is None:raise ValueError(f'empty authored part: {name}')
    part=part.crop(bounds);part.save(OUT/f'{name}-v{revision}.png')
    out[name]={'source':source,'region':region,'trim':bounds,'size':part.size}
 # Background/desk are the existing authored classroom, with identical proportions.
 shutil.copyfile(ROOT/'live_agent/generator/assets/vtuber_teacher/classroom.png',OUT/'classroom-v1.png')
 rig={
  'version':1,'model':'teacher-mesh-v1','renderer':'pixi-mesh','canvas':[480,864],
  'description':'Custom mesh-deformed adult anime teacher; not a Live2D/Cubism model.',
  'head_scale':.88,
  'neck_mask':[[158,155],[322,155],[322,325],[275,325],[274,345],[269,360],[267,425],[213,425],[211,360],[206,345],[205,325],[158,325]],
  'hair_physics':{'stiffness':35,'damping':10,'max_offset':2.6},
  'background':'classroom-v1.png','tabletop_y':575,'foreground_y':690,
  'supported_gestures':['idle','listen','explain','present','point','smile','think','nod','shake','wave'],
  'limits':{'head_turn':0.65,'head_tilt':0.045,'breath':1.6,'hair_sway':2.6,'gesture_weight':1},
  'layers':[
   {'id':'back-hair','group':'head','rect':[240,145,135,295],'grid':[9,15]},
   {'id':'face','group':'head','rect':[158,155,164,270],'grid':[13,19]},
   {'id':'body','group':'body','rect':[113,357,254,314],'grid':[15,19]},
   {'id':'left-arm','group':'arm','side':-1,'rect':[90,377,72,232],'grid':[9,27],
    'anchors':[[.30,.05],[.49,.52],[.745,.94]]},
   {'id':'right-arm','group':'arm','side':1,'rect':[318,377,72,232],'grid':[9,27],
    'anchors':[[.688,.05],[.516,.52],[.242,.94]]},
   {'id':'eyes','group':'head','rect':[179,262,122,32],'grid':[15,5]},
   {'id':'lids','group':'head','rect':[179,266,122,22],'grid':[15,5]},
   {'id':'brows','group':'head','rect':[179,250,122,15],'grid':[15,3]},
   {'id':'mouth-neutral','group':'head','rect':[218,295,44,30],'grid':[11,7]},
   {'id':'mouth-a','group':'head','rect':[218,291,44,36],'grid':[11,9]},
   {'id':'mouth-o','group':'head','rect':[222,293,36,34],'grid':[9,9]},
   {'id':'glasses','group':'head','rect':[166,257,148,38],'grid':[15,5]},
   {'id':'front-hair','group':'head','rect':[129,119,222,290],'grid':[19,23]},
  ],
  'hands':{'relaxed':{'asset':'relaxed-hand-v1.png','size':[31,68],'anchor':[.45,.29]},
           'open':{'asset':'open-hand-v1.png','size':[62,42],'anchor':[.80,.64]},
           # Authored hands contain a second sleeve. Runtime masks keep only
           # skin and register its wrist inside the continuous arm's cuff.
           'point':{'asset':'point-hand-v1.png','size':[48,56],'anchor':[.625,.645],
                    'skin_mask':[[0,0],[1,0],[1,.55],[.695,.564],[.68,.61],[.615,.68],[.555,.725],[0,.725]]},
           'wave':{'asset':'wave-hand-v1.png','size':[44,68],'anchor':[.53,.76],
                   'skin_mask':[[0,0],[1,0],[1,.694],[.681,.694],[.674,.739],[.519,.773],[.387,.751],[.378,.694],[0,.694]]}},
  'arms':{'shoulders':[[346,385],[134,385]],'elbows':[[359,501],[121,501]],'forearm_length':103,
          'rest_angle':-.48,'explain_angle':-1.10,'present_angle':-.91,'point_angle':.85},
  'extraction':out,
 }
 for layer in rig['layers']:layer['asset']=layer['id']+'-v1.png'
 if revision==2:
  rig['asset_revision']=2
  rig['camera']={'scale':1.10,'pivot':[240,575]}
  rig['head_scale']=.96
  rig['neck_mask']=None
  rig['collar_blend']=False
  rig['jaw_width']=.08
  positions={
   'back-hair':[241,155,132,278],'face':[130,136,220,332],
   'body':[106,340,268,332],
   'front-hair':[126,124,228,290],
   'eyes':[183,269,114,25],'lids':[183,273,114,18],
   'brows':[183,258,114,12],'glasses':[171,262,138,35],
   'mouth-neutral':[218,303,44,30],'mouth-a':[218,300,44,34],
   'mouth-o':[223,301,34,32]}
  for layer in rig['layers']:
   layer['asset']=layer['id']+'-v2.png'
   if layer['id'] in positions:layer['rect']=positions[layer['id']]
   if layer['id']=='right-arm':layer['anchors']=[[.431,.05],[.285,.52],[.695,.94]]
   if layer['id']=='left-arm':layer['anchors']=[[.514,.05],[.65,.52],[.278,.94]]
  rig['hands']['relaxed'].update(size=[38,74],anchor=[.49,.13])
  rig['hands']['open'].update(size=[72,48],anchor=[.88,.20])
  rig['hands']['point'].update(size=[58,66])
  rig['hands']['wave'].update(size=[56,76])
  for spec in rig['hands'].values():spec['asset']=spec['asset'].replace('-v1.png','-v2.png')
  rig['arms'].update(point_angle=.40,wave_upper_angle=.54,wave_angle=-2.927,
                     think_upper_angle=-.52,think_angle=-3.00)
 if revision==3:
  # Artist-authored adult silhouette. Keep each source tile's aspect ratio;
  # attachment coordinates, rather than fitted rectangles, define limb lengths.
  rig.update(asset_revision=3,head_scale=1,head_pivot=[240,378],
             neck_mask=None,collar_blend=False,jaw_width=0)
  def uniform(name,x,y,width):
   sw,sh=out[name]['size']
   return [x,y,width,width*sh/sw]
  positions={
   'body':uniform('body',75,325,330),
   'back-hair':uniform('back-hair',252,200,106),
   'face':uniform('face',157.5,195,165),
   'front-hair':uniform('front-hair',157,184,166),
   'eyes':uniform('eyes',198,290,84),
   'lids':uniform('lids',198,291,84),
   'brows':uniform('brows',198,281,84),
   'glasses':uniform('glasses',187,286,106),
   'mouth-neutral':uniform('mouth-neutral',224,320,32),
   'mouth-a':uniform('mouth-a',224,317,32),
   'mouth-o':uniform('mouth-o',227,318,26),
   'right-arm':uniform('right-arm',0,0,67),
   'left-arm':uniform('left-arm',0,0,67)}
  for layer in rig['layers']:
   layer['asset']=layer['id']+'-v3.png'
   layer['rect']=positions[layer['id']]
   if layer['id']=='right-arm':layer['anchors']=[[.519,.074],[.673,.508],[.285,.947]]
   if layer['id']=='left-arm':layer['anchors']=[[.481,.074],[.327,.508],[.715,.947]]
  # The front hair already includes the ponytail. An entire rear-view head
  # behind it creates a second crown in a frontal portrait.
  rig['layers']=[layer for layer in rig['layers'] if layer['id']!='back-hair']
  for name,spec in rig['hands'].items():
   spec['asset']=spec['asset'].replace('-v1.png','-v3.png')
   sw,sh=out[name+'-hand']['size']
   width={'relaxed':70,'open':79,'point':66,'wave':58}[name]
   spec['size']=[width,width*sh/sw]
  rig['hands']['relaxed'].update(anchor=[.83,.12],rest_rotation=-.45,contact_shadow=True)
  rig['hands']['open'].update(anchor=[.88,.20])
  rig['arms'].update(shoulders=[[360,375],[120,375]],elbows=[[369,507],[111,507]],
                     forearm_length=112,rest_angle=-.55,explain_angle=-1.10,
                     present_angle=-.91,point_angle=.30,
                     wave_upper_angle=.30,wave_angle=-2.88,
                     think_upper_angle=-.42,think_angle=-2.94)
 (OUT/f'rig-v{revision}.json').write_text(json.dumps(rig,indent=2)+'\n')
 print('Extracted',len(out),'authored layers and wrote',OUT/f'rig-v{revision}.json')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,choices=(1,2,3,4,5,6,7),default=7)
 build(parser.parse_args().revision)
