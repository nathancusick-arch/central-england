import streamlit as st
import pandas as pd
import io, tempfile, shutil, subprocess
from pathlib import Path
from copy import copy
from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter

COLUMN_MAP = {'Order': 'order_internal_id',
 'Client': 'client_name',
 'Visit': 'internal_id',
 'Site': 'site_internal_id',
 'Order Deadline': 'end_date',
 'Responsibility': 'responsibility',
 'Premises Name': 'site_name',
 'Address1': 'site_address_1',
 'Address2': 'site_address_2',
 'Address3': 'site_address_3',
 'City': None,
 'Post Code': 'site_post_code',
 'Submitted Date': 'submitted_date',
 'Approved Date': 'approval_date',
 'Item to order': 'item_to_order',
 'Actual Visit Date': 'date_of_visit',
 'Actual Visit Time': 'time_of_visit',
 'AM / PM': None,
 'Pass-Fail': 'primary_result',
 'Pass-Fail2': 'secondary_result',
 'Abort Reason': 'Please detail why you were unable to conduct this audit:',
 'Extra Site 1': 'site_code',
 'Extra Site 2': None,
 'Extra Site 3': None,
 'Extra Site 4': None,
 'Extra Site 5': None,
 'VISITORSEX': None,
 'What type of alcohol did you purchase?': ['What type of E-cigarette product did you purchase/attempt to purchase?',
                                            'What type of alcohol did you try to purchase?'],
 'Please give details of the alcohol purchased (brand and size):': ['Please give details of the e-cig product that you '
                                                                    'purchased:',
                                                                    'Please give details of the cigarettes that you purchased:',
                                                                    'Please give details of the alcohol that you purchased:'],
 'Did you make the purchase on its own or as part of a larger shop?': 'Did you make the purchase on its own or as part of a '
                                                                      'larger shop?',
 'Did the operator ask your age?': None,
 'Did the operator ask for your ID during the transaction?': 'Did the staff member who served you ask for ID?',
 'Did the operator make eye contact with you during the transaction?': 'Did the staff member who served you make eye contact '
                                                                       'with you during the transaction?',
 'If eye contact was made, when was it FIRST made?': 'When was eye contact first made?',
 'In your opinion, did the operator make an assessment of your age?': 'Did the staff member who served you look at you long '
                                                                      'enough to assess your age?  ',
 'Was the operator wearing a name badge?': 'Was the staff member who served you wearing a name badge?',
 'If they were, please state their name:': 'What was the name of the staff member who served you?',
 'Please accurately describe the operator that served you (include hair colour and style, build, height and any distinguishing features):': 'Please '
                                                                                                                                            'accurately '
                                                                                                                                            'describe '
                                                                                                                                            'the '
                                                                                                                                            'staff '
                                                                                                                                            'member '
                                                                                                                                            'who '
                                                                                                                                            'served '
                                                                                                                                            'you:',
 'Was there any "Challenge 25" signage visible in the till area?': "Was there any generic 'Challenge 25' material visible from "
                                                                   'the till?',
 'Was the operator wearing a "Challenge 25" Badge?': "Was the staff member wearing a 'Challenge 25' badge?",
 'OTHER VISIT DETAILS': None,
 'How many staff members were serving?': ['How many staff members were working on the tills?',
                                          'How staff members were working on the tills?'],
 'Please comment on the overall service you received (include queue length and unattended tills):': 'Please comment on the '
                                                                                                    'overall service you '
                                                                                                    'received:',
 'From the receipt, please enter the store name:': 'From the top of the receipt, please enter the store name:',
 'Please enter the receipt number (#000000):': 'Please enter the receipt number (#000000) from the receipt:',
 'Please enter the C number (C:000000):': 'Please enter the C number (C:000000) from the receipt:',
 'Please enter the T number (T:00):': 'Please enter the T number (T:00) from the receipt:',
 'Please describe the location and positions of the store (i.e. names of the stores on either side):': None,
 'Please use this space to explain anything unusual about your visit or to clarify any detail of your report:': 'Please use this '
                                                                                                                'space to '
                                                                                                                'explain '
                                                                                                                'anything '
                                                                                                                'unusual about '
                                                                                                                'your visit or '
                                                                                                                'to clarify any '
                                                                                                                'detail of your '
                                                                                                                'report:',
 'Please confirm below whether or not you were asked for ID:': ['Please confirm below whether or not you were asked for ID:',
                                                                'Please confirm whether or not you were asked for ID, and if so, '
                                                                'at what point during the transaction ID was requested:']}
REPORT_SHEETS=["Summary Data","Store Performance","Org Level Performance","DOW-TOD Performance","Performance over Time"]

def csv_df(f):
 b=f.getvalue()
 for e in ('utf-8-sig','utf-8','cp1252','latin1'):
  try:return pd.read_csv(io.BytesIO(b),encoding=e,low_memory=False)
  except UnicodeDecodeError:pass
 raise ValueError('Unsupported CSV encoding')

def map_data(df):
 out=pd.DataFrame(index=df.index); missing=[]
 for target,source in COLUMN_MAP.items():
  if source is None: out[target]=''
  elif isinstance(source,list):
   cols=[c for c in source if c in df]
   if not cols: missing+=source; out[target]=''
   else: out[target]=df[cols].apply(lambda r:' | '.join(str(v).strip() for v in r if pd.notna(v) and str(v).strip()),axis=1)
  elif source in df: out[target]=df[source]
  else: missing.append(source); out[target]=''
 for c in ['Order Deadline','Submitted Date','Approved Date','Actual Visit Date']: out[c]=pd.to_datetime(out[c],errors='coerce',dayfirst=True)
 return out,sorted(set(missing))

def month_of(df):
 d=pd.to_datetime(df['Actual Visit Date'],errors='coerce').dropna()
 if d.empty:d=pd.to_datetime(df['Approved Date'],errors='coerce').dropna()
 if d.empty:raise ValueError('No valid visit/approval dates')
 p=d.dt.to_period('M'); m=p.mode().iloc[0]
 if (p!=m).any():raise ValueError(f'Export contains {(p!=m).sum()} row(s) outside {m.strftime("%B %Y")}')
 return m

def stores(f):
 wb=load_workbook(io.BytesIO(f.getvalue()),data_only=True,read_only=True,keep_vba=True)
 if 'Coop Database' not in wb.sheetnames:raise ValueError("Store DB needs 'Coop Database'")
 rows=list(wb['Coop Database'].iter_rows(values_only=True)); h=[str(x).strip() if x is not None else '' for x in rows[0]]
 d=pd.DataFrame(rows[1:],columns=h); req=['Store Code','Site Internal ID','Area','Region','Area Name','Store Name']
 miss=[x for x in req if x not in d]
 if miss:raise ValueError('Store DB missing: '+', '.join(miss))
 d=d[d['Store Code'].notna()].copy(); d['Store Code']=d['Store Code'].astype(str).str.replace(r'\.0$','',regex=True).str.strip()
 if d['Store Code'].duplicated().any():raise ValueError('Duplicate Store Code values in Store DB')
 return d

def style(a,b):
 if a.has_style:b._style=copy(a._style)
 b.number_format=a.number_format;b.alignment=copy(a.alignment);b.protection=copy(a.protection)

def clear(ws,a,b):
 for row in ws.iter_rows(min_row=a,max_row=b):
  for c in row:
   if c.__class__.__name__!='MergedCell':c.value=None

def write_data(ws,df):
 hd={ws.cell(3,c).value:c for c in range(1,ws.max_column+1) if ws.cell(3,c).value is not None}; templ=4; end=3+len(df)
 if end>ws.max_row:ws.insert_rows(ws.max_row+1,end-ws.max_row)
 clear(ws,4,ws.max_row)
 for r,(_,x) in enumerate(df.iterrows(),4):
  for n,v in x.items():
   if n in hd:ws.cell(r,hd[n]).value=None if pd.isna(v) else (v.to_pydatetime() if isinstance(v,pd.Timestamp) else v)
  for c in range(1,ws.max_column+1):
   style(ws.cell(templ,c),ws.cell(r,c))
   if c>len(COLUMN_MAP) and isinstance(ws.cell(templ,c).value,str) and ws.cell(templ,c).value.startswith('='):
    try:ws.cell(r,c).value=Translator(ws.cell(templ,c).value,origin=ws.cell(templ,c).coordinate).translate_formula(ws.cell(r,c).coordinate)
    except:ws.cell(r,c).value=ws.cell(templ,c).value
 ws['A2']=f'=COUNTA(A4:A{end})';ws['IJ2']=f'=COUNTA(IL4:IR{end})';ws['IK2']=f'=COUNTA(IK4:IK{end})';ws['IL2']=f'=COUNTA(IL4:IL{end})'

def region(ws,d):
 clear(ws,1,ws.max_row);ws.cell(1,5,'Operations Manager');ws.cell(1,6,'Group Manager')
 for r,(_,x) in enumerate(d.iterrows(),2):
  vals=[x['Store Code']]*3+[x['Store Name'],x['Area Name'],x['Region']]
  for c,v in enumerate(vals,1):ws.cell(r,c,v)
 for r,v in enumerate(sorted(set(d['Area Name'].dropna().astype(str))),1):ws.cell(r,7,v)

def pf(sheet,data,col,r,m):
 q=f"'{data}'!${col}$4:${col}$1048576";k=f"'{sheet}'!$A{r}"
 if m=='v':return f'=COUNTIF({q},{k}&"PASS")+COUNTIF({q},{k}&"FAIL")+COUNTIF({q},{k}&"ABORT")'
 if m=='c':return f'=COUNTIF({q},{k}&"PASS")+COUNTIF({q},{k}&"FAIL")'
 if m=='f':return f'=COUNTIF({q},{k}&"FAIL")'
 return f'=COUNTIF({q},{k}&"PASS")'

def store_perf(ws,d):
 clear(ws,7,ws.max_row)
 for r,(_,x) in enumerate(d.iterrows(),7):
  ws.cell(r,1,x['Store Code']);ws.cell(r,2,x['Store Name'])
  for c,m in zip(range(3,7),'vcfp'):ws.cell(r,c,pf('Store Performance','This Period','IS',r,m))
  ws.cell(r,7,f'=IF(D{r}=0,"-",F{r}/D{r})')
  for c,m in zip(range(8,12),'vcfp'):ws.cell(r,c,pf('Store Performance','R12M','IS',r,m))
  ws.cell(r,12,f'=IF(I{r}=0,"-",K{r}/I{r})')
  for c in range(1,13):style(ws.cell(7,c),ws.cell(r,c))
 r=7+len(d);ws.cell(r,1,'Total')
 for c in [3,4,5,6,8,9,10,11]:ws.cell(r,c,f'=SUM({get_column_letter(c)}7:{get_column_letter(c)}{r-1})')
 ws.cell(r,7,f'=IF(D{r}=0,"-",F{r}/D{r})');ws.cell(r,12,f'=IF(I{r}=0,"-",K{r}/I{r})')
 return r

def org_perf(ws,d):
 clear(ws,7,ws.max_row);r=7;tot=[]
 for label,col,names in [('Area','IB',sorted(set(d['Area Name'].dropna().astype(str)))),('Manager','IA',sorted(set(d['Region'].dropna().astype(str))))]:
  first=r
  for n in names:
   ws.cell(r,1,n)
   for c,m in zip(range(2,6),'vcfp'):ws.cell(r,c,pf('Org Level Performance','This Period',col,r,m))
   ws.cell(r,6,f'=IF(C{r}=0,"-",E{r}/C{r})')
   for c,m in zip(range(7,11),'vcfp'):ws.cell(r,c,pf('Org Level Performance','R12M',col,r,m))
   ws.cell(r,11,f'=IF(H{r}=0,"-",J{r}/H{r})');r+=1
  ws.cell(r,1,'Total')
  for c in [2,3,4,5,7,8,9,10]:ws.cell(r,c,f'=SUM({get_column_letter(c)}{first}:{get_column_letter(c)}{r-1})')
  ws.cell(r,6,f'=IF(C{r}=0,"-",E{r}/C{r})');ws.cell(r,11,f'=IF(H{r}=0,"-",J{r}/H{r})');tot.append(r);r+=2
 return tot


def norm(v):
 return '' if v is None else str(v).strip().casefold()

def sync_region(ws,d):
 """Update or append only Store DB rows that differ; preserve all unchanged and historical rows."""
 rows={str(ws.cell(r,1).value).replace('.0','').strip():r for r in range(2,ws.max_row+1) if ws.cell(r,1).value is not None}
 changed=[]; added=[]
 last=max(rows.values(),default=1)
 for _,x in d.iterrows():
  code=str(x['Store Code']).strip(); desired=[code,code,code,x['Store Name'],x['Area Name'],x['Region']]
  if code in rows:
   r=rows[code]
   if any(norm(ws.cell(r,c).value)!=norm(desired[c-1]) for c in range(1,7)):
    for c,v in enumerate(desired,1): ws.cell(r,c).value=v
    changed.append(code)
  else:
   last+=1
   for c,v in enumerate(desired,1): ws.cell(last,c).value=v
   added.append(code); rows[code]=last
 return changed,added

def sync_store_performance(ws,d):
 """Leave existing rows untouched; update changed names and insert genuinely new Store DB sites."""
 total=next((r for r in range(7,ws.max_row+1) if ws.cell(r,1).value=='Total'),ws.max_row+1)
 rows={str(ws.cell(r,1).value).replace('.0','').strip():r for r in range(7,total) if ws.cell(r,1).value is not None}
 changed=[]; added=[]
 for _,x in d.iterrows():
  code=str(x['Store Code']).strip(); name=x['Store Name']
  if code in rows:
   if norm(ws.cell(rows[code],2).value)!=norm(name): ws.cell(rows[code],2,name); changed.append(code)
  else:
   ws.insert_rows(total,1)
   r=total; src=max(7,r-1)
   for c in range(1,13): style(ws.cell(src,c),ws.cell(r,c))
   ws.cell(r,1,code); ws.cell(r,2,name)
   for c,mx in zip(range(3,7),'vcfp'): ws.cell(r,c,pf('Store Performance','This Period','IS',r,mx))
   ws.cell(r,7,f'=IF(D{r}=0,"-",F{r}/D{r})')
   for c,mx in zip(range(8,12),'vcfp'): ws.cell(r,c,pf('Store Performance','R12M','IS',r,mx))
   ws.cell(r,12,f'=IF(I{r}=0,"-",K{r}/I{r})')
   rows[code]=r; added.append(code); total+=1
 if changed or added:
  for c in [3,4,5,6,8,9,10,11]: ws.cell(total,c,f'=SUM({get_column_letter(c)}7:{get_column_letter(c)}{total-1})')
  ws.cell(total,1,'Total'); ws.cell(total,7,f'=IF(D{total}=0,"-",F{total}/D{total})'); ws.cell(total,12,f'=IF(I{total}=0,"-",K{total}/I{total})')
 return changed,added,total

def current_org_labels(ws):
 labels=[]
 for r in range(7,ws.max_row+1):
  v=ws.cell(r,1).value
  if v not in (None,'Total'): labels.append(str(v).strip())
 return set(labels)

def sync_org_performance(ws,d):
 """Rebuild the organisational list only when the Store DB introduces a previously absent area or manager."""
 wanted=set(d['Area Name'].dropna().astype(str).str.strip())|set(d['Region'].dropna().astype(str).str.strip())
 missing=sorted(wanted-current_org_labels(ws))
 if not missing: return False,[],[]
 # Preserve historical organisational labels needed by rolling-12-month reporting.
 existing=current_org_labels(ws)
 area=set(d['Area Name'].dropna().astype(str).str.strip())
 managers=set(d['Region'].dropna().astype(str).str.strip())
 # Existing labels not identifiable as a current manager remain in the area section.
 area=sorted(area | (existing-managers)); managers=sorted(managers)
 clear(ws,7,ws.max_row); r=7; totals=[]
 for col,names in [('IB',area),('IA',managers)]:
  first=r
  for n in names:
   ws.cell(r,1,n)
   for c,mx in zip(range(2,6),'vcfp'): ws.cell(r,c,pf('Org Level Performance','This Period',col,r,mx))
   ws.cell(r,6,f'=IF(C{r}=0,"-",E{r}/C{r})')
   for c,mx in zip(range(7,11),'vcfp'): ws.cell(r,c,pf('Org Level Performance','R12M',col,r,mx))
   ws.cell(r,11,f'=IF(H{r}=0,"-",J{r}/H{r})'); r+=1
  ws.cell(r,1,'Total')
  for c in [2,3,4,5,7,8,9,10]: ws.cell(r,c,f'=SUM({get_column_letter(c)}{first}:{get_column_letter(c)}{r-1})')
  ws.cell(r,6,f'=IF(C{r}=0,"-",E{r}/C{r})'); ws.cell(r,11,f'=IF(H{r}=0,"-",J{r}/H{r})'); totals.append(r); r+=2
 return True,missing,totals

def generate(a,b,c):
 raw=csv_df(a);cur,missing=map_data(raw);m=month_of(cur);d=stores(c)
 wb=load_workbook(io.BytesIO(b.getvalue()),data_only=False)
 req=['Checks','Region','This Period','R12M']+REPORT_SHEETS
 bad=[x for x in req if x not in wb.sheetnames]
 if bad:raise ValueError('LIVE report missing: '+', '.join(bad))
 wb['Checks']['B19']=m.to_timestamp().to_pydatetime();wb['Checks']['B19'].number_format='mmmm yy';write_data(wb['This Period'],cur)
 rs=wb['R12M'];heads=list(COLUMN_MAP.keys());old=[]
 for r in range(4,rs.max_row+1):
  if rs.cell(r,1).value is not None:old.append([rs.cell(r,z).value for z in range(1,len(COLUMN_MAP)+1)])
 hist=pd.DataFrame(old,columns=heads);hist['Actual Visit Date']=pd.to_datetime(hist['Actual Visit Date'],errors='coerce');start=(m-11).to_timestamp()
 hist=hist[(hist['Actual Visit Date']>=start)&(hist['Actual Visit Date']<m.to_timestamp())];roll=pd.concat([hist,cur],ignore_index=True).drop_duplicates('Visit',keep='last');write_data(rs,roll)
 r_changed,r_added=sync_region(wb['Region'],d); s_changed,s_added,sr=sync_store_performance(wb['Store Performance'],d); o_updated,o_missing,ot=sync_org_performance(wb['Org Level Performance'],d); wb.calculation.fullCalcOnLoad=True;wb.calculation.forceFullCalc=True;wb.calculation.calcMode='auto'
 stem=f"Central England Test Purchases Report - {m.strftime('%B %Y')}"
 with tempfile.TemporaryDirectory() as td:
  live=Path(td)/(stem+' LIVE.xlsx');wb.save(live);lo=shutil.which('libreoffice') or shutil.which('soffice')
  if lo:
   out=Path(td)/'recalc';out.mkdir();subprocess.run([lo,'--headless','--convert-to','xlsx','--outdir',str(out),str(live)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
   if (out/live.name).exists():shutil.copy2(out/live.name,live)
  non=load_workbook(live,data_only=False)
  if lo:
   vals=load_workbook(live,data_only=True)
   for sn in REPORT_SHEETS:
    for row in non[sn].iter_rows():
     for cell in row:
      if isinstance(cell.value,str) and cell.value.startswith('='):cell.value=vals[sn][cell.coordinate].value
   for sn in list(non.sheetnames):
    if sn not in REPORT_SHEETS:del non[sn]
   # Rebuild the visible 12-month trend directly from the rolling data so the static report is not dependent on array-formula support.
   trend=non['Performance over Time']; rd=pd.to_datetime(roll['Actual Visit Date'],errors='coerce'); result=roll['Pass-Fail'].astype(str).str.upper()
   months=pd.period_range(end=m,periods=12,freq='M')
   for col,mp in enumerate(months,2):
    mask=rd.dt.to_period('M').eq(mp); passed=(result[mask]=='PASS').sum(); failed=(result[mask]=='FAIL').sum(); completed=passed+failed
    trend.cell(6,col,passed/completed if completed else '-')
  np=Path(td)/(stem+'.xlsx');non.save(np);lb=live.read_bytes();nb=np.read_bytes()
 return lb,nb,stem,{'period':m.strftime('%B %Y'),'export_rows':len(raw),'rolling_rows':len(roll),'stores':len(d),'areas':d['Area Name'].nunique(),'managers':d['Region'].nunique(),'missing_optional_columns':missing,'store_total_row':sr,'org_total_rows':ot,'region_updated':bool(r_changed or r_added),'region_changed_codes':r_changed,'region_added_codes':r_added,'store_performance_updated':bool(s_changed or s_added),'store_name_changes':s_changed,'store_additions':s_added,'org_level_performance_updated':o_updated,'new_org_labels':o_missing,'recalculated':bool(lo)}

st.set_page_config(page_title='Central England Report Generator',layout='wide')
st.title('Central England Report Generator')
st.write('Upload the new audit export, previous LIVE report and current Store Database. The Store DB is treated as the source of truth for site, area and manager structures.')
a=st.file_uploader('Audit export (.csv)',type=['csv']);b=st.file_uploader('Previous LIVE report (.xlsx)',type=['xlsx']);c=st.file_uploader('Store Database (.xlsm/.xlsx)',type=['xlsm','xlsx'])
if a and b and c:
 try:
  live,non,stem,audit=generate(a,b,c);st.success(f"Generated {audit['period']} for {audit['export_rows']:,} audits and {audit['stores']:,} stores.");st.json(audit);x,y=st.columns(2)
  with x:st.download_button('Download LIVE report',live,stem+' LIVE.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
  with y:st.download_button('Download non-LIVE report',non,stem+'.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
 except Exception as e:st.exception(e)
