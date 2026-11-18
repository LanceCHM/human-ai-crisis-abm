from pathlib import Path
import sys,csv

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
OUT=Path(__file__).resolve().parent

plt.rcParams.update({'font.family':'DejaVu Sans','axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'path'})
with (OUT/'作图用逐团队差异.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
names=['S3-G1','S3-G2','S3-R','S3-ALT','R-ALT']
blue='#247A9B';orange='#CB7048';gray='#ADB6C2'
fig,ax=plt.subplots(figsize=(11,8.5))
fig.subplots_adjust(left=.17,right=.97,top=.88,bottom=.12)
ax.set_ylim(4.7,-.7)
ax.axhspan(1.55,4.6,color='#F3F5F7',zorder=0)
rng=np.random.default_rng(20261102)
for y,name in enumerate(names):
    x=np.array([float(r['gain_difference_pp']) for r in rows if r['contrast']==name])
    assert len(x)==200
    jitter=rng.uniform(-.19,.19,len(x))
    c=np.where(x>1e-10,blue,np.where(x< -1e-10,orange,gray))
    ax.scatter(x,y+jitter,s=36,c=c,alpha=.67,linewidths=0,zorder=3)
ax.set_yticks(range(5),[s.replace('-',' − ') for s in names],fontsize=17)
ax.set_xticks([-30,-20,-10,0,10,20]);ax.tick_params(axis='x',labelsize=16)
ax.tick_params(axis='both',length=0,pad=12)
ax.axvline(0,color='#697686',ls='--',lw=1.5,zorder=2)
ax.grid(axis='x',color='#DEE4EB',lw=.8)
ax.spines[['top','right','left']].set_visible(False)
ax.spines['bottom'].set_color('#BAC4CF')
ax.set_xlabel('Difference in learning gains (percentage points)',fontsize=18,labelpad=18)
handles=[Line2D([0],[0],marker='o',ls='',color=c,label=t,markersize=9) for c,t in zip([blue,gray,orange],['Positive: first group higher','Zero: equal','Negative: first group lower'])]
ax.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,1.035),frameon=False,ncol=3,fontsize=11,columnspacing=1.9,handletextpad=.5,borderaxespad=0)
for ext in ['png','pdf','svg']:fig.savefig(OUT/f'Figure_3.{ext}',dpi=450,facecolor='white')
fig.savefig(OUT/'Figure_3_preview.png',dpi=110,facecolor='white')
