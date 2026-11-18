from pathlib import Path
import sys,csv
from decimal import Decimal,ROUND_HALF_UP

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
OUT=Path(__file__).resolve().parent

plt.rcParams.update({'font.family':'DejaVu Sans','axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'path'})
with (OUT/'经验覆盖与调用_作图数据.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
keys=['total_new_pairs','new_lag1_pairs','retained_lag1_exit0','retained_lag1_exit1','early_memory_use_percent','early_brier']
values=np.array([[float(r[k]) for k in keys] for r in rows])
# Each column has its own zero-to-maximum scale; color always means numerical magnitude.
scaled=values/values.max(axis=0)
soft='--soft' in sys.argv
contrast='--contrast' in sys.argv
palette=['#F7F9FC','#D3E4F3','#8CB9DC','#427FAE','#173F6B'] if contrast else (['#F5F6F8','#DCE5EE','#A2B9CF'] if soft else ['#F3F5F7','#AED0DE','#287B99'])
cmap=colors.LinearSegmentedColormap.from_list('magnitude',palette)
fig,ax=plt.subplots(figsize=(13.6,6.7))
fig.subplots_adjust(left=.185,right=.975,top=.72,bottom=.28)
fig.text(.055,.94,'Experience, condition coverage, and early judgments',fontsize=18,weight='bold',color='#232E3C')
fig.text(.055,.881,'200 simulated teams per group; cells show team means. Color indicates magnitude within each column, not performance.',fontsize=9,color='#526071')
ax.imshow(scaled,cmap=cmap,vmin=0,vmax=1,aspect='auto')
ax.set_xticks(range(6),['All new\npairs','New pairs\nwith lag 1','Exit 0\nretained lag-1 cases','Exit 1\nretained lag-1 cases','Early memory\nuse (%)','Early judgment error\nBrier score ↓'])
ax.xaxis.tick_top();ax.tick_params(axis='x',length=0,pad=12,labelsize=9)
ax.set_yticks(range(5),['G1  Routine AI','G2  Fixed','S3  Current practical','R  Random','ALT  Alternating'])
ax.tick_params(axis='y',length=0,pad=12,labelsize=9)
ax.set_xticks(np.arange(-.5,6,1),minor=True);ax.set_yticks(np.arange(-.5,5,1),minor=True)
ax.grid(which='minor',color='white',linewidth=3);ax.tick_params(which='minor',length=0)
for spine in ax.spines.values():spine.set_visible(False)
for i in range(5):
    for j in range(6):
        digits=0 if j==4 else (5 if j==5 else 2)
        q=Decimal(str(values[i,j])).quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP)
        s=f'{q:.{digits}f}'+('%' if j==4 else '')
        if contrast:
            rgb=cmap(scaled[i,j])[:3]
            linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
            luminance=sum(c*w for c,w in zip(linear,[.2126,.7152,.0722]))
            text_color='white' if luminance<.179 else '#172B40'
        else:
            text_color='#23364B' if soft else ('white' if scaled[i,j]>.72 else '#232E3C')
        ax.text(j,i,s,ha='center',va='center',fontsize=13,color=text_color,weight='bold' if i==2 else 'normal')
notes=[
 'Columns 1–2: new pairs over 60 training events; columns 3–4: cases retained at training end. Lag 1 = one simulation step between readings.',
 'Early use: tasks in which at least one exit uses memory at the earliest judgment; 100% does not imply use for both exits or complete coverage.',
 'Colors are scaled separately to each column maximum and cannot be compared across columns. Lower Brier is better; exits have not yet failed.',
 'Results describe coverage, retrieval, and judgment under the specified retrieval rules; they do not isolate a causal effect of matching itself.'
]
for i,t in enumerate(notes):fig.text(.055,.205-.041*i,t,fontsize=8.5,color='#526071')
suffix='层次增强版' if contrast else ('柔和蓝灰版' if soft else '单图版')
for ext in ['png','pdf','svg']:fig.savefig(OUT/f'Figure_4.{ext}',dpi=300,facecolor='white')
fig.savefig(OUT/'Figure_4_preview.png',dpi=110,facecolor='white')
