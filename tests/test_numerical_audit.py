"""Casos FICTICIOS para auditoría de software, nunca evidencia de mercado."""
import importlib.util
import unittest
HAS_DEPS=importlib.util.find_spec('numpy') is not None and importlib.util.find_spec('scipy') is not None
if HAS_DEPS:
    import numpy as np
    from microtrade.feature_study import step
    from microtrade.numerical_audit import objective,derivatives,finite_difference,newton,audit_case,scipy_objective


@unittest.skipUnless(HAS_DEPS,'Dependencias opcionales: requirements-audit.txt')
class NumericalAuditTests(unittest.TestCase):
    def setUp(self):
        self.x=np.column_stack((np.ones(40),np.sin(np.arange(40)),np.cos(np.arange(40)*.7)))
        self.y=(np.arange(40)%3==0).astype(int)
        self.recipe={'learning_rate':.001,'l2':.01}

    def test_exact_objective_scaling_gradient_and_unpenalized_intercept(self):
        w=np.array([.4,.2,-.3]);g,_=derivatives(w,self.x,self.y,.01)
        np.testing.assert_allclose(g,finite_difference(w,self.x,self.y,.01),atol=2e-9,rtol=0)
        self.assertAlmostEqual(objective(w,self.x,self.y,.01),scipy_objective(w,self.x,self.y,.01),places=14)
        g0,_=derivatives(w,self.x,self.y,0)
        self.assertEqual(g[0],g0[0]);np.testing.assert_allclose(g[1:]-g0[1:],.01*w[1:],atol=1e-14)
        # El objetivo es media, no suma: duplicar filas no cambia valor/gradiente.
        xx=np.concatenate((self.x,self.x));yy=np.concatenate((self.y,self.y))
        self.assertAlmostEqual(objective(w,xx,yy,.01),objective(w,self.x,self.y,.01),places=14)
        np.testing.assert_allclose(derivatives(w,xx,yy,.01)[0],g,atol=1e-14)

    def test_independent_solvers_and_recorded_epoch10_reconstruction(self):
        w=np.zeros(3)
        for _ in range(10):
            for row,label in zip(self.x,self.y):w=step(w,row,int(label),self.recipe)
        r=audit_case(self.x,self.y,self.recipe,w.tolist())
        self.assertTrue(r['scipy_success']);self.assertEqual(r['recorded_weight_max_error'],0)
        self.assertLess(r['solver_max_probability_difference'],1e-5)
        self.assertEqual([p['epochs'] for p in r['trajectory']],[0,1,10,100,1000])
        self.assertGreater(r['trajectory'][2]['gap_to_optimum'],0)

    def test_budget_and_single_class_fail_closed(self):
        with self.assertRaises(ValueError):audit_case(self.x,self.y,self.recipe,max_epochs=10)
        with self.assertRaises(ValueError):audit_case(self.x,np.zeros(40,dtype=int),self.recipe)

    def test_changed_recorded_weights_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'pesos'):
            audit_case(self.x,self.y,self.recipe,[100,100,100])
