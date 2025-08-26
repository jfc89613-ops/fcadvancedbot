import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, precision_recall_fscore_support
def evaluate_probs(y_true, p):
    auc=roc_auc_score(y_true, p); brier=brier_score_loss(y_true, p)
    y_hat=(p>=0.5).astype(int)
    prec,rec,f1,_=precision_recall_fscore_support(y_true, y_hat, average="binary", zero_division=0)
    return {"auc":auc,"brier":brier,"precision":prec,"recall":rec,"f1":f1}
