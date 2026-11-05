"""Merge the 3x3 layout into existing resources, retaining icon/text sizes."""
import copy

METRICS={'launcherGridTop':'24dp','launcherGridWidth':'372dp','launcherItemGap':'18dp'}
UNCHANGED={'launcherItemWidth':'112dp','launcherItemHeight':'112dp','launcherIconTileSize':'92dp',
           'launcherIconSize':'92dp','launcherLabelGap':'4dp','launcherTitleBoxHeight':'16dp'}

def prepare_documents(constants,launcher,template):
    constants,launcher,template=copy.deepcopy((constants,launcher,template))
    metric=constants['data']['ui']['content']['metric']
    for key,value in UNCHANGED.items():
        if metric.get(key)!=value:raise ValueError('Unexpected existing size; inspect before changing: '+key)
    if metric['y']!='40dp':raise ValueError('Unexpected desktop content offset')
    metric.update(METRICS)
    content=launcher['children'][0]
    grid=next(n for n in content['children'] if n['id']=='grid_stage')
    assert grid['commonProps']['scrollable']
    grid['placement']['height']=372
    assert any(n['id']=='pages' for n in content['children'])
    nodes={n['id']:n for n in template['node']['children']}
    nodes['icon_box']['placement'].update(mode='absolute',x=10,y=0)
    nodes['title_box']['placement'].update(mode='absolute',x=0,y=96)
    nodes['title_box'].setdefault('bindings',{})['placement.x']='label_x'
    return constants,launcher,template

def geometry(visible_count):
    """Visible content layout; transparent button corners may extend beyond round glass."""
    cells=[]
    for row in range(3):
        for col in range(3):
            cells.append({'x':54+col*130,'y':64+row*130,'width':112,'height':112,
                          'icon_width':92,'icon_height':92,
                          'label_x':24 if row==2 and col==0 else -24 if row==2 and col==2 else 0})
    assert max(c['y']+112 for c in cells)<442
    return {'columns':3,'rows':3,'page_size':9,'pages':max(1,(visible_count+8)//9),
            'grid_x':54,'grid_y':64,'grid_width':372,'grid_height':372,'gap':18,'cells':cells}
