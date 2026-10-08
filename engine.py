import math
from statistics import NormalDist
import numpy as np

def sex_code(sex):
    s=str(sex).lower().strip()
    if s in ('masculino','hombre','m','1','1.0'): return 1
    if s in ('femenino','mujer','f','2','2.0'): return 0
    raise ValueError('Sexo inválido')

def calculate(age,sex,pas,pad,measured=None):
    age,pas,pad=float(age),float(pas),float(pad)
    male=sex_code(sex)
    if not 9<=age<=87: raise ValueError('Edad fuera del intervalo de referencia: 9–87')
    if not (70<=pas<=260 and 50<=pad<=180 and pas>pad): raise ValueError('PAS/PAD inválidas')
    if measured is not None:
        measured=float(measured)
        if not 2<=measured<=30: raise ValueError('VOP medida inválida')
    pam=pad+0.4*(pas-pad)
    arg=.180526+.916427*math.log10(age)+.010667*age+.000396061*age**2+.133136*male+.043184*pam
    europe=4.62-.13*age+.0018*age**2+.0006*age*pam+.0284*pam
    euro_risk=9.587-.402*age+.004560*age**2-2.621e-5*age**2*pam+3.176e-3*age*pam-.01832*pam
    if male:
        mu=1.3942+3.4927*math.log10(age)-.02436*age+5.698e-4*age**2
        sd=-.04760+.06798*math.sqrt(age)+.02987*age-2.091e-4*age**2
    else:
        mu=.062441+5.3108*math.log10(age)-.09658*age+1.151e-3*age**2
        sd=1.0392-.4128*math.sqrt(age)+.08020*age-3.65e-4*age**2
    if sd<=0: raise ValueError('DE normativa no válida')
    normal=NormalDist()
    z=(measured-mu)/sd if measured is not None else None
    return {'Edad':age,'Sexo':'Masculino' if male else 'Femenino','PAS':pas,'PAD':pad,'PAM':pam,
        'ePWV_ARG':arg,'ePWV_Europa_sana':europe,'ePWV_Europa_riesgo':euro_risk,
        'Diaz_media':mu,'Diaz_DE':sd,'Diaz_P90':mu+normal.inv_cdf(.9)*sd,
        'Diaz_P95':mu+normal.inv_cdf(.95)*sd,'VOP_medida':measured,'Z_medida':z,
        'Percentil_medida':100*normal.cdf(z) if z is not None else None,
        'Error_ARG':arg-measured if measured is not None else None,
        'Error_Europa':europe-measured if measured is not None else None}

def metrics(obs,pred):
    y=np.asarray(obs,float); p=np.asarray(pred,float); mask=np.isfinite(y)&np.isfinite(p)
    y,p=y[mask],p[mask]
    if len(y)<2: raise ValueError('Se requieren >=2 pares')
    e=p-y; bias=float(e.mean()); sd=float(e.std(ddof=1))
    sst=float(((y-y.mean())**2).sum())
    return {'N':len(y),'Sesgo':bias,'MAE':float(abs(e).mean()),
       'RMSE':float(np.sqrt((e**2).mean())),
       'R2':float(1-(e**2).sum()/sst) if sst else float('nan'),
       'LoA_inf':bias-1.96*sd,'LoA_sup':bias+1.96*sd}
