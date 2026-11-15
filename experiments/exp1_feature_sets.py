"""Run from the repo root after run_all.py. Compares model versions with leave-one-lake-out CV."""
import sys, numpy as np
sys.path.insert(0, '.')
from glw import model as M
from glw.data import get_chip, get_static
from glw.zones import ZONES
from sklearn.ensemble import HistGradientBoostingClassifier
C = 'data/chips'  # 2021 chips + static files from a run_all.py cache
rng = np.random.default_rng(0)
D = {}
for z in ZONES:
    chip = get_chip(z, 2021, C); st = get_static(z, C)
    F = M.make_features(chip['bands'], st['slope'], chip['scl'])
    v = M.valid_mask(chip); t = st['worldcover'] == 80
    D[z['id']] = (F, v, t, chip, z['split'])

def ratio_feats(F):
    b,g,r,n,s1,s2 = F[:6]; e=1e-6
    return np.stack([F[6], F[7], F[8], (s1-n)/(s1+n+e), (b-n)/(b+n+e), (g-r)/(g+r+e), (s2-s1)/(s2+s1+e), F[10], F[11], F[12], F[13]])

def table(zids, fsel, sample=True):
    X=[];Y=[]
    for zid in zids:
        F,v,t,_,_=D[zid]; G=fsel(F); x=G[:,v].T; y=t[v]
        if sample:
            w=np.where(y)[0]; l=np.where(~y)[0]
            k=rng.choice(l,size=min(len(l),max(4*len(w),20000)),replace=False)
            idx=np.concatenate([w,k]); x=x[idx]; y=y[idx]
        X.append(x);Y.append(y)
    return np.concatenate(X),np.concatenate(Y)

def f1(p,y):
    tp=(p&y).sum(); return 2*tp/max(2*tp+(p&~y).sum()+(~p&y).sum(),1)

train=[z['id'] for z in ZONES if z['split']=='train']
cfgs = {
 'A_current_all': (lambda F:F, dict(max_leaf_nodes=31,l2_regularization=1.0)),
 'B_reg_all': (lambda F:F, dict(max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5.0,max_iter=100)),
 'C_ratios': (ratio_feats, dict(max_leaf_nodes=31,l2_regularization=1.0)),
 'D_ratios_reg': (ratio_feats, dict(max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5.0,max_iter=100)),
 'E_ratios_noesa': (lambda F: ratio_feats(F)[:8], dict(max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5.0,max_iter=100)),
}
ths=np.arange(0.3,0.96,0.05)
res={}
for name,(fs,kw) in cfgs.items():
    # leave-one-training-lake-out CV: choose threshold
    cvf=np.zeros(len(ths)); 
    for hold in train:
        X,Y=table([t for t in train if t!=hold],fs)
        clf=HistGradientBoostingClassifier(random_state=0,**kw).fit(X,Y)
        F,v,t,_,_=D[hold]; pr=clf.predict_proba(fs(F)[:,v].T)[:,1]
        for i,th in enumerate(ths): cvf[i]+=f1(pr>=th,t[v])
    cvf/=len(train); bi=cvf.argmax()
    X,Y=table(train,fs); clf=HistGradientBoostingClassifier(random_state=0,**kw).fit(X,Y)
    out={}
    for grp in ['test_himalaya','test_andes']:
        tp=fp=fn=0
        for zid,(F,v,t,_,s) in D.items():
            if s!=grp: continue
            p=clf.predict_proba(fs(F)[:,v].T)[:,1]>=ths[bi]; y=t[v]
            tp+=(p&y).sum(); fp+=(p&~y).sum(); fn+=(~p&y).sum()
        out[grp]=round(2*tp/(2*tp+fp+fn),3)
    res[name]=(round(cvf[0.5==ths.round(2)].item() if any(ths.round(2)==0.5) else 0,3), round(ths[bi],2), round(cvf[bi],3), out)
    print(name, 'CV@0.5', res[name][0], 'best th', res[name][1], 'CV', res[name][2], 'TEST', out, flush=True)
# NDWI ref
for grp in ['test_himalaya','test_andes']:
    tp=fp=fn=0
    for zid,(F,v,t,_,s) in D.items():
        if s!=grp: continue
        p=(F[6]>0.2)[v]; y=t[v]; tp+=(p&y).sum(); fp+=(p&~y).sum(); fn+=(~p&y).sum()
    print('NDWI>0.2',grp,round(2*tp/(2*tp+fp+fn),3))
