"""Auditoría del objetivo logístico: gradiente, Newton y SciPy independiente.

No recibe ventanas externas ni elige configuraciones mediante scores de mercado.
"""
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_expit
from .feature_study import step


def objective(w,x,y,l2):
    z=x@w
    return float(np.mean(np.logaddexp(0,z)-y*z)+.5*l2*(w[1:]@w[1:]))


def derivatives(w,x,y,l2):
    z=x@w
    p=np.exp(-np.logaddexp(0,-z))
    gradient=x.T@(p-y)/len(y)
    gradient[1:]+=l2*w[1:]
    hessian=(x.T*(p*(1-p)))@x/len(y)
    hessian[1:,1:]+=l2*np.eye(len(w)-1)
    return gradient,hessian


def scipy_objective(w,x,y,l2):
    # Otra expresión estable; el solver NO recibe nuestro gradiente ni Hessiano.
    z=x@w
    return float(-np.mean(y*log_expit(z)+(1-y)*log_expit(-z))+.5*l2*np.sum(np.square(w[1:])))


def finite_difference(w,x,y,l2,epsilon=1e-6):
    gradient=np.zeros_like(w)
    for j in range(len(w)):
        delta=np.zeros_like(w); delta[j]=epsilon
        gradient[j]=(objective(w+delta,x,y,l2)-objective(w-delta,x,y,l2))/(2*epsilon)
    return gradient


def newton(x,y,l2):
    w=np.zeros(x.shape[1])
    for iteration in range(100):
        g,h=derivatives(w,x,y,l2)
        if np.max(np.abs(g))<1e-10:return w,iteration
        direction=np.linalg.solve(h,g); alpha=1.; old=objective(w,x,y,l2)
        for _ in range(60):
            candidate=w-alpha*direction
            if objective(candidate,x,y,l2)<=old-1e-4*alpha*float(g@direction):
                w=candidate;break
            alpha*=.5
        else:raise ValueError('Newton no supera búsqueda de paso.')
    raise ValueError('Newton no converge.')


def audit_case(x,y,recipe,recorded=None,max_epochs=1000):
    if max_epochs!=1000 or x.shape[0]!=len(y) or not np.isfinite(x).all() or set(y)!={0,1}:
        raise ValueError('Caso/presupuesto inválido; se requieren ambas clases.')
    l2=recipe['l2']; probe=np.sin(np.arange(x.shape[1])+1)*.2
    g,h=derivatives(probe,x,y,l2); fd=finite_difference(probe,x,y,l2)
    gradient_error=float(np.max(np.abs(g-fd)))
    # El promedio de gradientes de pasos de producción debe ser el gradiente batch.
    production=np.mean([(probe-step(probe,row,int(label),recipe))/recipe['learning_rate'] for row,label in zip(x,y)],axis=0)
    step_error=float(np.max(np.abs(g-production)))
    eigen_min=float(np.linalg.eigvalsh(h)[0])
    if gradient_error>2e-7 or step_error>2e-10 or eigen_min<=0:
        raise ValueError('Gradiente/penalización/Hessiano no pasa controles.')
    wn,iterations=newton(x,y,l2)
    reference=minimize(scipy_objective,np.zeros(x.shape[1]),args=(x,y,l2),method='L-BFGS-B',jac='3-point',
                       options={'ftol':1e-15,'gtol':1e-9,'maxiter':2000,'maxls':50})
    ws=reference.x; ln=objective(wn,x,y,l2); ls=objective(ws,x,y,l2)
    agreement=float(np.max(np.abs(wn-ws)))
    prediction_agreement=float(np.max(np.abs(np.exp(-np.logaddexp(0,-x@wn))-np.exp(-np.logaddexp(0,-x@ws)))))
    reference_gradient=float(np.max(np.abs(derivatives(ws,x,y,l2)[0])))
    if not reference.success or abs(ln-ls)>1e-9 or agreement>1e-4 or prediction_agreement>1e-5 or reference_gradient>1e-7:
        raise ValueError('Soluciones independientes no concuerdan.')
    w=np.zeros(x.shape[1]); checkpoints=[]; maximum_logit=0.; original=None
    for epoch in range(1001):
        if epoch in (0,1,10,100,1000):
            loss=objective(w,x,y,l2); norm=float(np.max(np.abs(derivatives(w,x,y,l2)[0])))
            checkpoints.append({'epochs':epoch,'objective':loss,'gap_to_optimum':loss-ln,'gradient_inf':norm})
            maximum_logit=max(maximum_logit,float(np.max(np.abs(x@w))))
            if epoch==10:original=w.copy()
        if epoch==1000:break
        for row,label in zip(x,y):
            maximum_logit=max(maximum_logit,abs(float(w@row)))
            w=step(w,row,int(label),recipe)
    maximum_logit=max(maximum_logit,float(np.max(np.abs(x@wn))),float(np.max(np.abs(x@ws))))
    if maximum_logit>=35:raise ValueError('Clipping activo: objetivo suave no equivalente.')
    recorded_error=None if recorded is None else float(np.max(np.abs(original-np.array(recorded))))
    if recorded_error is not None and recorded_error>1e-10:
        raise ValueError('No reconstruye pesos del experimento ya registrado.')
    return {'rows':len(y),'parameters':x.shape[1],'gradient_fd_max_error':gradient_error,
            'production_step_max_error':step_error,'hessian_min_eigenvalue':eigen_min,
            'newton_iterations':iterations,'newton_objective':ln,'scipy_objective':ls,
            'solver_max_weight_difference':agreement,'solver_max_probability_difference':prediction_agreement,
            'scipy_gradient_inf':reference_gradient,'scipy_success':bool(reference.success),
            'maximum_abs_logit':maximum_logit,'recorded_weight_max_error':recorded_error,
            'trajectory':checkpoints,'epochs10_converged_at_gradient_1e7':checkpoints[2]['gradient_inf']<=1e-7}
