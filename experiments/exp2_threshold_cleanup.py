exec(open('experiments/exp1_feature_sets.py').read().split("train=[z['id']")[0])
from scipy import ndimage
def clean(mask, n=10):
    lab,k=ndimage.label(mask)
    if k==0: return mask
    sz=ndimage.sum(mask,lab,range(1,k+1)); keep=np.zeros(k+1,bool); keep[1:]=sz>=n
    return keep[lab]
train=[z['id'] for z in ZONES if z['split']=='train']
cfgs = {
 'B_reg_all': (lambda F:F, dict(max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5.0,max_iter=100)),
 'D_ratios_reg': (ratio_feats, dict(max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5.0,max_iter=100)),
}
def predmap(clf,fs,F,v,th,cl):
    p=np.zeros(v.shape,bool); p[v]=clf.predict_proba(fs(F)[:,v].T)[:,1]>=th
    return clean(p) if cl else p
for name,(fs,kw) in cfgs.items():
  for cl in [False, True]:
    for th in [0.45,0.5,0.6]:
        cv=0
        for hold in train:
            X,Y=table([t for t in train if t!=hold],fs)
            clf=HistGradientBoostingClassifier(random_state=0,**kw).fit(X,Y)
            F,v,t,_,_=D[hold]; cv+=f1(predmap(clf,fs,F,v,th,cl)[v],t[v])
        cv/=len(train)
        X,Y=table(train,fs); clf=HistGradientBoostingClassifier(random_state=0,**kw).fit(X,Y)
        out={}
        for grp in ['test_himalaya','test_andes']:
            tp=fp=fn=0
            for zid,(F,v,t,_,s) in D.items():
                if s!=grp: continue
                p=predmap(clf,fs,F,v,th,cl)[v]; y=t[v]
                tp+=(p&y).sum(); fp+=(p&~y).sum(); fn+=(~p&y).sum()
            out[grp]=round(2*tp/(2*tp+fp+fn),3)
        print(name,'clean' if cl else 'raw',th,'CV',round(cv,3),'TEST',out,flush=True)
for cl in [False,True]:
  for grp in ['test_himalaya','test_andes']:
    tp=fp=fn=0
    for zid,(F,v,t,_,s) in D.items():
        if s!=grp: continue
        p=np.zeros(v.shape,bool); p[v]=(F[6]>0.2)[v]; p=clean(p) if cl else p; p=p[v]; y=t[v]
        tp+=(p&y).sum(); fp+=(p&~y).sum(); fn+=(~p&y).sum()
    print('NDWI', 'clean' if cl else 'raw', grp, round(2*tp/(2*tp+fp+fn),3))
