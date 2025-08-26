import numpy as np
from sklearn.model_selection import KFold
class PurgedKFold:
    def __init__(self, n_splits=5, embargo_frac=0.01):
        self.n_splits=n_splits; self.embargo_frac=embargo_frac
    def split(self, X, t1):
        n=len(X); kf=KFold(n_splits=self.n_splits, shuffle=False)
        for tr,te in kf.split(np.arange(n)):
            emb=int(len(te)*self.embargo_frac); ts,te_ = te[0], te[-1]
            tr=tr[(tr<(ts-emb)) | (tr>(te_+emb))]; yield tr, te
