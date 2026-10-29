"""Shared resource edits for fresh builds and reversible on-device installation."""
def theme_card():
    return {'type':'templateRef','id':'desktop_theme_card','templateId':'settings_card','overrides':{'.':{'style':{'padding':'${constant.settings.layout.cardPadding}'},'placement':{'mode':'flow','width':'match','height':'wrap','alignSelf':'stretch'}}},'slots':{'content':[
        {'type':'label','id':'title','labelProps':{'text':'桌面主题'},'styleRefs':['app.cardTitle'],'style':{'font':'${font.desktop_theme}'},'placement':{'mode':'flow','width':'match','height':'wrap'}},
        {'type':'dropdown','id':'choice','dropdownProps':{'options':['经典Q版','赛博朋克'],'selectedIndex':0},'bindings':{'dropdownProps.selectedIndex':'selected'},'events':[{'type':'valueChanged','action':'settings.display.desktop_theme'}],'placement':{'mode':'flow','width':'match','height':'56dp'},'style':{'font':'${font.desktop_theme}','fontSize':24,'bgColor':'#fff1df','textColor':'#533b32','radius':10,'padding':6}}
    ]}}
def update_display(doc):
    page=next(n for n in doc['children'] if n['id']=='page')
    page['children']=[theme_card()]+[n for n in page['children'] if n['id']!='desktop_theme_card']
    return doc
def update_button(doc):
    def scan(n):
        if n.get('id')=='label' and 'labelProps.text' in n.get('bindings',{}):n['bindings']['style.textColor']='theme_text'
        for child in n.get('children',[]):scan(child)
    scan(doc['node']);return doc
def update_launcher(doc):
    content=doc['children'][0]
    next(n for n in content['children'] if n['id']=='pages')['bindings']['style.textColor']='theme_text'
    next(n for n in content['children'] if n['id']=='grid_stage')['placement']['height']=242
    return doc
def cyber_images(manifest):
    images=[{'id':'cyber.'+app,'src':'/sdcard/themes/cyberpunk-v1/'+name,'width':92,'height':92,'preload':True} for app,name in manifest['icons'].items()]
    images.append({'id':'cyber.wallpaper','src':'/sdcard/themes/cyberpunk-v1/wallpaper.bin','width':486,'height':486,'preload':True})
    return images
