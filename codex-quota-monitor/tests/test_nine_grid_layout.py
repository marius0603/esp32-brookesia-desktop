import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nine_grid_resources import prepare_documents,geometry,UNCHANGED

class LayoutTests(unittest.TestCase):
 def fixtures(self):
  metrics=dict(UNCHANGED,y='40dp',launcherGridTop='16dp',launcherGridWidth='372dp',launcherItemGap='18dp')
  return ({'data':{'ui':{'content':{'metric':metrics},'metric':{'captionFont':'14sp'},'color':{'custom':'#123456'}}}},
          {'children':[{'children':[{'id':'grid_stage','commonProps':{'scrollable':True},'placement':{'height':242},'custom':'retained'},{'id':'pages','bindings':{'style.textColor':'theme_text'}}]}]}, {'node':{'children':[{'id':'icon_box','placement':{}},{'id':'title_box','placement':{}}]}})
 def test_preserves_sizes_fonts_colors_and_unknown_fields(self):
  a,b,t=self.fixtures();before=copy.deepcopy((a,b,t));c,d,u=prepare_documents(a,b,t)
  self.assertEqual((a,b,t),before)
  for key,value in UNCHANGED.items():self.assertEqual(c['data']['ui']['content']['metric'][key],value)
  self.assertEqual(c['data']['ui']['metric'],a['data']['ui']['metric']);self.assertEqual(c['data']['ui']['color'],a['data']['ui']['color'])
  self.assertEqual(d['children'][0]['children'][0]['custom'],'retained')
  self.assertEqual(d['children'][0]['children'][1],b['children'][0]['children'][1])
 def test_nine_cells_gap_labels_and_footer(self):
  g=geometry(13);self.assertEqual((g['pages'],g['page_size'],g['grid_x'],g['grid_y']),(2,9,54,64))
  self.assertEqual(len(g['cells']),9)
  self.assertEqual(g['gap'],18)
  self.assertEqual([g['cells'][i]['label_x'] for i in [6,7,8]],[24,0,-24])
  self.assertLess(max(c['y']+112 for c in g['cells']),442)
  for i,a in enumerate(g['cells']):
   for b in g['cells'][i+1:]:self.assertFalse(a['x']<b['x']+b['width'] and b['x']<a['x']+a['width'] and a['y']<b['y']+b['height'] and b['y']<a['y']+a['height'])
 def test_partial_empty_and_full_pages(self):
  self.assertEqual([geometry(n)['pages'] for n in [0,4,9,10,13,18,19]],[1,1,1,2,2,2,3])
 def test_unexpected_sizes_are_rejected(self):
  a,b,t=self.fixtures();a['data']['ui']['content']['metric']['launcherIconSize']='80dp'
  with self.assertRaises(ValueError):prepare_documents(a,b,t)

if __name__=='__main__':unittest.main()
