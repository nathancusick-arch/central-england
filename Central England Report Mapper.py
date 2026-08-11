import io, re, copy
from datetime import datetime, time
from pathlib import Path
import pandas as pd
import streamlit as st
from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.chartsheet.chartsheet import Chartsheet

COLUMN_MAP = {
"Order":"order_internal_id","Client":"client_name","Visit":"internal_id","Site":"site_internal_id",
"Order Deadline":"end_date","Responsibility":"responsibility","Premises Name":"site_name",
"Address1":"site_address_1","Address2":"site_address_2","Address3":"site_address_3","City":None,
"Post Code":"site_post_code","Submitted Date":"submitted_date","Approved Date":"approval_date",
"Item to order":"item_to_order","Actual Visit Date":"date_of_visit","Actual Visit Time":"time_of_visit",
"AM / PM":None,"Pass-Fail":"primary_result","Pass-Fail2":"secondary_result",
"Abort Reason":"Please detail why you were unable to conduct this audit:","Extra Site 1":"site_code",
"Extra Site 2":None,"Extra Site 3":None,"Extra Site 4":None,"Extra Site 5":None,"VISITORSEX":None,
"What type of alcohol did you purchase?":["What type of E-cigarette product did you purchase/attempt to purchase?","What type of alcohol did you try to purchase?"],
"Please give details of the alcohol purchased (brand and size): ":["Please give details of the e-cig product that you purchased:","Please give details of the cigarettes that you purchased:","Please give details of the alcohol that you purchased:"],
"Did you make the purchase on its own or as part of a larger shop?":"Did you make the purchase on its own or as part of a larger shop?",
"Did the operator ask your age?":"Did the staff member who served you ask your age?",
"Did the operator ask for your ID during the transaction?":"Did the staff member who served you ask for ID?",
"Did the operator make eye contact with you during the transaction?":"Did the staff member who served you make eye contact with you during the transaction?",
"If eye contact was made, when was it FIRST made?":"When was eye contact first made?",
"In your opinion, did the operator make an assessment of your age?":["Did the staff member who served you look at you long enough to assess your age?","Did the staff member who served you look at you long enough to assess your age?  "],
"Was the operator wearing a name badge?":"Was the staff member who served you wearing a name badge?",
"If they were, please state their name:":"What was the name of the staff member who served you?",
"Please accurately describe the operator that served you (include hair colour and style, build, height and any distinguishing features):":"Please accurately describe the staff member who served you:",
"Was there any \"Challenge 25\" signage visible in the till area?":"Was there any generic 'Challenge 25' material visible from the till?",
"Was the operator wearing a \"Challenge 25\" Badge?":"Was the staff member wearing a 'Challenge 25' badge?",
"OTHER VISIT DETAILS":None,
"How many staff members were serving?":["How many staff members were working on the tills?","How staff members were working on the tills?"],
"Please comment on the overall service you received (include queue length and unattended tills):":"Please comment on the overall service you received:",
"From the receipt, please enter the store name:":"From the top of the receipt, please enter the store name:",
"Please enter the receipt number (#000000):":"Please enter the receipt number (#000000) from the receipt:",
"Please enter the C number (C:000000):":"Please enter the C number (C:000000) from the receipt:",
"Please enter the T number (T:00):":"Please enter the T number (T:00) from the receipt:",
"Please describe the location and positions of the store (i.e. names of the stores on either side):":None,
"Please use this space to explain anything unusual about your visit or to clarify any detail of your report:":"Please use this space to explain anything unusual about your visit or to clarify any detail of your report:",
"Please confirm below whether or not you were asked for ID:":["Please confirm below whether or not you were asked for ID:","Please confirm whether or not you were asked for ID, and if so, at what point during the transaction ID was requested:"]}
RAW_SHEETS={'Checks','Input','Region','Sheet1','This Period','R12M'}
REPORT_SHEETS=['Summary Data','Store Performance','Org Level Performance','DOW-TOD Performance','Performance over Time']


def text(v): return '' if pd.isna(v) else str(v).strip()
def code(v):
 s=text(v); return s[:-2] if s.endswith('.0') else s
def value_from(row,m):
 if m is None:return ''
 if isinstance(m,list):
  vals=[text(row.get(x,'')) for x in m]; return ' | '.join(v for v in vals if v)
 return text(row.get(m,''))
def read_csv(f):
 b=f.getvalue() if hasattr(f,'getvalue') else Path(f).read_bytes()
 return pd.read_csv(io.BytesIO(b),dtype=str,keep_default_na=False)
def read_db(f):
 b=f.getvalue() if hasattr(f,'getvalue') else Path(f).read_bytes()
 x=pd.read_excel(io.BytesIO(b),sheet_name='Coop Database',engine='openpyxl',dtype=str)
 x.columns=[text(c) for c in x.columns]
 out=pd.DataFrame({'Store Code':x['Store Code'].map(code),'Store Name':x['Store Name'].map(text),
 'Area Name':x.get('Area',x.get('Area Name','')).map(text),'Region':x.get('Region','').map(text)})
 return out[out['Store Code']!=''].drop_duplicates('Store Code',keep='last')
def filtered(df):
 item=df.get('item_to_order',pd.Series('',index=df.index)).astype(str).str.strip().str.casefold()
 result=df.get('primary_result',pd.Series('',index=df.index)).astype(str).str.strip().str.casefold()
 return df[(item!='rapid delivery') & (result!='abort')].copy()
def mapped(df):
 out=pd.DataFrame(index=df.index)
 for k,m in COLUMN_MAP.items(): out[k]=df.apply(lambda r:value_from(r,m),axis=1)
 for c in ['Order Deadline','Submitted Date','Approved Date','Actual Visit Date']:
  out[c]=pd.to_datetime(out[c],dayfirst=True,errors='coerce')
 def tm(v):
  try:return datetime.strptime(str(v).strip()[:5],'%H:%M').time()
  except:return None
 out['Actual Visit Time']=out['Actual Visit Time'].map(tm)
 out['Extra Site 1']=out['Extra Site 1'].map(code)
 out['Pass-Fail']=out['Pass-Fail'].str.strip().str.lower()
 return out

def neutral_styles(ws,start=4,end=None):
 end=min(end or ws.max_row,start+100); result={}
 for c in range(1,ws.max_column+1):
  counts={}
  for r in range(start,end+1):
   cell=ws.cell(r,c); counts[cell.style_id]=counts.get(cell.style_id,0)+1
  sid=max(counts,key=counts.get)
  result[c]=copy.copy(next(ws.cell(r,c)._style for r in range(start,end+1) if ws.cell(r,c).style_id==sid))
 return result

def clear_rows(ws,first,last=None):
 from openpyxl.cell.cell import MergedCell
 last=last or ws.max_row
 for rg in list(ws.merged_cells.ranges):
  if rg.max_row>=first: ws.unmerge_cells(str(rg))
 for row in ws.iter_rows(min_row=first,max_row=last):
  for c in row:
   if not isinstance(c,MergedCell): c.value=None

def write_raw(ws,df):
 # Preserve formula templates before clearing and use predominant neutral styles.
 formula_templates={c:ws.cell(4,c).value for c in range(1,ws.max_column+1) if isinstance(ws.cell(4,c).value,str) and ws.cell(4,c).value.startswith('=')}
 styles=neutral_styles(ws,4)
 clear_rows(ws,4)
 headers={ws.cell(3,c).value:c for c in range(1,ws.max_column+1) if ws.cell(3,c).value}
 for i,(_,row) in enumerate(df.iterrows(),4):
  for h,v in row.items():
   c=headers.get(h)
   if c:
    cell=ws.cell(i,c); cell._style=copy.copy(styles[c]); cell.value=v
    # neutralise legacy manual exception highlighting in raw data
    cell.font=copy.copy(cell.font); cell.font=Font(name=cell.font.name or 'Arial',size=cell.font.sz or 10,bold=cell.font.b,italic=cell.font.i,color='000000')
    cell.fill=PatternFill(fill_type=None)
    if h in ('Order Deadline','Submitted Date','Approved Date','Actual Visit Date'):cell.number_format='dd/mm/yyyy'
    elif h=='Actual Visit Time':cell.number_format='hh:mm'
    elif h=='Extra Site 1':
     try:cell.value=int(code(v));cell.number_format='0'
     except:cell.value=code(v)
  for c,f in formula_templates.items():
   cell=ws.cell(i,c); cell._style=copy.copy(styles[c]); cell.value=Translator(f,origin=f'{get_column_letter(c)}4').translate_formula(f'{get_column_letter(c)}{i}')
 return len(df)

def raw_records(df,db):
 z=df.copy(); lookup=db.set_index('Store Code').to_dict('index')
 z['_code']=z['Extra Site 1'].map(code)
 z['_area']=z['_code'].map(lambda x:lookup.get(x,{}).get('Area Name',''))
 z['_region']=z['_code'].map(lambda x:lookup.get(x,{}).get('Region',''))
 z['_result']=z['Pass-Fail'].str.lower()
 z['_date']=pd.to_datetime(z['Actual Visit Date'],errors='coerce')
 z['_time']=z['Actual Visit Time']
 z['_dow']=z['_date'].dt.day_name().str[:3]
 def tod(t):
  if not isinstance(t,time):return ''
  m=t.hour*60+t.minute
  if 7*60<=m<12*60:return 'Morning'
  if 12*60<=m<17*60:return 'Afternoon'
  return 'Night'
 z['_tod']=z['_time'].map(tod)
 return z

def metrics(d,field,labels):
 rows=[]
 for label in labels:
  q=d[d[field].astype(str)==str(label)]
  comp=int(q['_result'].isin(['pass','fail']).sum()); p=int((q['_result']=='pass').sum()); f=int((q['_result']=='fail').sum())
  rows.append((label,comp,comp,p,f,p/comp if comp else 0))
 return rows

def copy_row_style(ws,src,dst,maxcol):
 for c in range(1,maxcol+1): ws.cell(dst,c)._style=copy.copy(ws.cell(src,c)._style)
 ws.row_dimensions[dst].height=ws.row_dimensions[src].height

def write_metric_sheet(ws,rows_tp,rows_r12,total_gaps=False):
 # rows are aligned label metrics; write contiguous from row 7 and a total immediately after
 clear_rows(ws,7)
 by12={str(x[0]):x for x in rows_r12}
 r=7
 for x in rows_tp:
  copy_row_style(ws,7,r,ws.max_column); y=by12.get(str(x[0]),(x[0],0,0,0,0,0))
  vals=[x[0],x[1],x[2],x[3],x[4],x[5],y[1],y[2],y[3],y[4],y[5]]
  if ws.max_column==12: vals=[x[0],None,x[1],x[2],x[3],x[4],x[5],y[1],y[2],y[3],y[4],y[5]]
  for c,v in enumerate(vals,1): ws.cell(r,c,v)
  r+=1
 copy_row_style(ws,6,r,ws.max_column)
 ws.cell(r,1,'Total')
 # totals from input records, with duplicate site/name column handled
 tp=[sum(x[j] for x in rows_tp) for j in range(1,5)]; rr=[sum(x[j] for x in rows_r12) for j in range(1,5)]
 pr=tp[2]/tp[1] if tp[1] else 0; rrpr=rr[2]/rr[1] if rr[1] else 0
 vals=[None,tp[0],tp[1],tp[2],tp[3],pr,rr[0],rr[1],rr[2],rr[3],rrpr] if ws.max_column==12 else [tp[0],tp[1],tp[2],tp[3],pr,rr[0],rr[1],rr[2],rr[3],rrpr]
 for c,v in enumerate(vals,2 if ws.max_column==12 else 2): ws.cell(r,c,v)
 for row in range(7,r+1):
  for c in range(1,ws.max_column+1):
   if c in ([7,12] if ws.max_column==12 else [6,11]): ws.cell(row,c).number_format='0.0%'
 return r

def write_store(ws,tp,r12,db):
 existing=[]
 for r in range(7,ws.max_row+1):
  v=ws.cell(r,1).value
  if v not in (None,'Total') and code(v) not in existing:existing.append(code(v))
 db_codes=db['Store Code'].tolist(); labels=existing+[x for x in db_codes if x not in existing]
 names={code(ws.cell(r,1).value):text(ws.cell(r,2).value) for r in range(7,ws.max_row+1) if ws.cell(r,1).value not in (None,'Total')}
 names.update(db.set_index('Store Code')['Store Name'].to_dict())
 a=metrics(tp,'_code',labels); b=metrics(r12,'_code',labels)
 clear_rows(ws,7); by12={x[0]:x for x in b}; r=7
 for x in a:
  copy_row_style(ws,7,r,12); y=by12[x[0]]
  ws.cell(r,1,int(x[0]) if x[0].isdigit() else x[0]); ws.cell(r,1).number_format='0'; ws.cell(r,2,names.get(x[0],''))
  for c,v in zip(range(3,8),x[1:]):ws.cell(r,c,v)
  for c,v in zip(range(8,13),y[1:]):ws.cell(r,c,v)
  ws.cell(r,7).number_format=ws.cell(r,12).number_format='0.0%'; r+=1
 copy_row_style(ws,6,r,12); ws.cell(r,1,'Total')
 ta=[sum(x[j] for x in a) for j in range(1,5)]; tb=[sum(x[j] for x in b) for j in range(1,5)]
 vals=ta+[ta[2]/ta[1] if ta[1] else 0]+tb+[tb[2]/tb[1] if tb[1] else 0]
 for c,v in zip(range(3,13),vals):ws.cell(r,c,v)
 ws.cell(r,7).number_format=ws.cell(r,12).number_format='0.0%'
 return r

def write_org(ws,tp,r12,db):
 labels=[]
 for r in range(7,ws.max_row+1):
  v=ws.cell(r,1).value
  if v not in (None,'Total') and text(v) not in labels:labels.append(text(v))
 wanted=[]
 for x in pd.concat([db['Area Name'],db['Region']]).map(text).tolist():
  if x and x not in wanted: wanted.append(x)
 labels += [x for x in wanted if x not in labels]
 a=[];b=[]
 for lab in labels:
  qa=tp[(tp['_area']==lab)|(tp['_region']==lab)]; qb=r12[(r12['_area']==lab)|(r12['_region']==lab)]
  a+=metrics(qa.assign(_label=lab),'_label',[lab]); b+=metrics(qb.assign(_label=lab),'_label',[lab])
 return write_metric_sheet(ws,a,b)
def write_dowtod(ws,tp,r12):
 labels=[text(ws.cell(r,1).value) for r in range(7,ws.max_row+1) if ws.cell(r,1).value not in (None,'Total')]
 a=[];b=[]
 for lab in labels:
  fld='_dow' if lab[:3] in {'Mon','Tue','Wed','Thu','Fri','Sat','Sun'} else '_tod'
  key=lab[:3] if fld=='_dow' else lab
  a+=metrics(tp.assign(_label=tp[fld]),'_label',[key]); a[-1]=(lab,)+a[-1][1:]
  b+=metrics(r12.assign(_label=r12[fld]),'_label',[key]); b[-1]=(lab,)+b[-1][1:]
 return write_metric_sheet(ws,a,b)
def write_pot(ws,r12):
 # Preserve the row/column layout and write monthly pass rates as values; chart sheet references B6:M6.
 for c in range(2,14):
  month=ws.cell(5,c).value
  if isinstance(month,datetime): m=month.month
  elif isinstance(month,(int,float)): m=int(month)
  else:
   try:m=datetime.strptime(str(month)[:3],'%b').month
   except:m=c-1
  q=r12[r12['_date'].dt.month==m]; comp=q['_result'].isin(['pass','fail']).sum(); p=(q['_result']=='pass').sum()
  ws.cell(6,c,p/comp if comp else 0); ws.cell(6,c).number_format='0.0%'

def update_region(ws,db):
 rows={code(ws.cell(r,1).value):r for r in range(2,ws.max_row+1) if ws.cell(r,1).value is not None}; last=max(rows.values(),default=1)
 for _,x in db.iterrows():
  k=x['Store Code']; desired=[int(k) if k.isdigit() else k,int(k) if k.isdigit() else k,int(k) if k.isdigit() else k,x['Store Name'],x['Area Name'],x['Region']]
  r=rows.get(k)
  if not r:last+=1;r=last;rows[k]=r
  for c,v in enumerate(desired,1):ws.cell(r,c,v)

def clean_names(wb):
 for name in list(wb.defined_names):
  dn=wb.defined_names[name]
  if '#REF!' in str(dn.attr_text): del wb.defined_names[name]

def validate(path,expected_rows,nonlive=False):
 # Structural validation and XML parse; catches repaired-formula/chart corruption before delivery.
 import zipfile, xml.etree.ElementTree as ET
 with zipfile.ZipFile(path) as z:
  for n in z.namelist():
   if n.endswith('.xml') or n.endswith('.rels'):ET.fromstring(z.read(n))
 wb=load_workbook(path,data_only=False)
 assert 'Performance over Time' in wb.sheetnames
 assert any(isinstance(s,Chartsheet) and s.title=='Performance over Time Chart' and len(s._charts)==1 for s in wb._sheets)
 if nonlive:
  assert wb.active.title=='Summary Data'
 else:
  for sn in ['This Period','R12M']:
   ws=wb[sn]; formula_count=sum(1 for row in ws.iter_rows(min_row=4) for c in row if isinstance(c.value,str) and c.value.startswith('='))
   assert formula_count>expected_rows
  assert len(wb.defined_names)==1 and 'days' in wb.defined_names
 for sn in ['Store Performance','Org Level Performance','DOW-TOD Performance']:
  ws=wb[sn]; assert any(ws.cell(r,3).value not in (None,0) for r in range(7,ws.max_row+1))
 return True

def generate(csv_file,previous_file,db_file):
 src=filtered(read_csv(csv_file)); new=mapped(src); db=read_db(db_file)
 b=previous_file.getvalue() if hasattr(previous_file,'getvalue') else Path(previous_file).read_bytes()
 wb=load_workbook(io.BytesIO(b),data_only=False)
 # Prior R12M raw values plus current period, then dedupe and retain latest 12 months.
 oldws=wb['R12M']; header_col={}
 for c in range(1,51):
  h=oldws.cell(3,c).value
  if h in COLUMN_MAP and h not in header_col: header_col[h]=c
 old=pd.DataFrame([{h:oldws.cell(r,c).value for h,c in header_col.items()} for r in range(4,oldws.max_row+1)])
 combined=pd.concat([old,new],ignore_index=True); combined=combined.drop_duplicates('Visit',keep='last')
 dates=pd.to_datetime(combined['Actual Visit Date'],dayfirst=True,errors='coerce'); ref=pd.to_datetime(new['Actual Visit Date'],errors='coerce').max()
 if pd.notna(ref):combined=combined[dates>=ref-pd.DateOffset(months=11)].copy()
 update_region(wb['Region'],db)
 write_raw(wb['This Period'],new); write_raw(wb['R12M'],combined)
 tp=raw_records(new,db); r12=raw_records(combined,db)
 write_store(wb['Store Performance'],tp,r12,db); write_org(wb['Org Level Performance'],tp,r12,db); write_dowtod(wb['DOW-TOD Performance'],tp,r12); write_pot(wb['Performance over Time'],r12)
 # UK date formats throughout relevant report/raw cells.
 for sn in ['This Period','R12M','Summary Data','Performance over Time']:
  ws=wb[sn]
  for row in ws.iter_rows():
   for c in row:
    if isinstance(c.value,(datetime,pd.Timestamp)):c.number_format='dd/mm/yyyy'
 clean_names(wb); wb.calculation.fullCalcOnLoad=True;wb.calculation.forceFullCalc=True;wb.calculation.calcMode='auto'
 out_live=io.BytesIO();wb.save(out_live)
 # non-LIVE: keep report tabs and chart sheet, remove support/raw sheets, set Summary Data active.
 for sn in list(RAW_SHEETS):
  if sn in wb.sheetnames:del wb[sn]
 wb.active=wb.sheetnames.index('Summary Data')
 out_non=io.BytesIO();wb.save(out_non)
 stem=f"Central England Test Purchases Report - {ref.strftime('%B %Y') if pd.notna(ref) else 'Generated'}"
 return out_live.getvalue(),out_non.getvalue(),stem,{'input_rows':len(src),'r12_rows':len(combined)}

st.set_page_config(page_title='Central England Report Generator',layout='wide')
st.title('Central England Report Generator')
st.caption('Generates fully validated LIVE and non-LIVE workbooks without LibreOffice round-tripping.')
a=st.file_uploader('Current audit export CSV',type=['csv']); b=st.file_uploader('Previous LIVE report',type=['xlsx']); c=st.file_uploader('Store DB',type=['xlsm','xlsx'])
if a and b and c:
 try:
  live,non,stem,audit=generate(a,b,c)
  lp=f'/tmp/{stem} LIVE.xlsx';np=f'/tmp/{stem}.xlsx';Path(lp).write_bytes(live);Path(np).write_bytes(non)
  validate(lp,audit['input_rows'],False);validate(np,audit['input_rows'],True)
  st.success(f"Validated successfully. {audit['input_rows']} current rows; {audit['r12_rows']} rolling rows.")
  st.download_button('Download LIVE report',live,f'{stem} LIVE.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  st.download_button('Download non-LIVE report',non,f'{stem}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
 except Exception as e: st.exception(e)
