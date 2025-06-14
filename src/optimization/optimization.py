############################################################################
### QPMwP - OPTIMIZATION
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     18.01.2025
# First version:    18.01.2025
# --------------------------------------------------------------------------



# Standard library imports
from abc import ABC, abstractmethod
from typing import Optional

# Third party imports
import numpy as np
import pandas as pd

# Local modules
from helper_functions import to_numpy
from estimation.covariance import Covariance
from estimation.expected_return import ExpectedReturn
from estimation.black_litterman import (
    bl_posterior_mean,
    generate_views_from_scores,
)
from optimization.optimization_data import OptimizationData
from optimization.constraints import Constraints
from optimization.quadratic_program import QuadraticProgram





# TODO:

# [ ] Add classes:
#    [x] MinVariance
#    [ ] MaxReturn
#    [ ] MaxSharpe
#    [ ] MaxUtility
#    [ ] RiskParity







class Objective():

    '''
    A class to handle the objective function of an optimization problem.

    Parameters:
    kwargs: Keyword arguments to initialize the coefficients dictionary. E.g. P, q, constant.
    '''

    def __init__(self, **kwargs):
        self.coefficients = kwargs

    @property #ensures the input is always a dictoinary
    def coefficients(self) -> dict:
        return self._coefficients

    @coefficients.setter
    def coefficients(self, value: dict) -> None:
        if isinstance(value, dict):
            self._coefficients = value
        else:
            raise ValueError('Input value must be a dictionary.')
        return None




class OptimizationParameter(dict):

    '''
    A class to handle optimization parameters.

    Parameters:
    kwargs: Additional keyword arguments to initialize the dictionary.
    '''

    def __init__(self, **kwargs):
        super().__init__(
            solver_name = 'cvxopt',
        ) #initializes with default solver = cvxopt
        self.update(kwargs)



class Optimization(ABC): #setting objectives, solving problems, handling results

    '''
    Abstract base class for optimization problems.

    Parameters:
    params (OptimizationParameter): Optimization parameters.
    kwargs: Additional keyword arguments.
    '''

    def __init__(self,
                 params: Optional[OptimizationParameter] = None,
                 constraints: Optional[Constraints] = None,
                 **kwargs):
        self.params = OptimizationParameter() if params is None else params
        self.params.update(**kwargs)
        self.constraints = Constraints() if constraints is None else constraints
        self.objective: Objective = Objective()
        self.results = {}

    @abstractmethod
    def set_objective(self, optimization_data: OptimizationData) -> None:
        raise NotImplementedError(
            "Method 'set_objective' must be implemented in derived class."
        )

    @abstractmethod
    def solve(self) -> None:

        # TODO:
        # Check consistency of constraints
        # self.check_constraints()

        # Get the coefficients of the objective function
        obj_coeff = self.objective.coefficients
        if 'P' not in obj_coeff.keys() or 'q' not in obj_coeff.keys():
            raise ValueError("Objective must contain 'P' and 'q'.")

        # Ensure that P and q are numpy arrays (so that they could be used in qp solvers)
        obj_coeff['P'] = to_numpy(obj_coeff['P'])
        obj_coeff['q'] = to_numpy(obj_coeff['q'])

        self.solve_qpsolvers()
        return None

    def solve_qpsolvers(self) -> None:

        self.model_qpsolvers()
        self.model.solve()

        solution = self.model.results['solution']
        status = solution.found
        ids = self.constraints.ids
        # weights = pd.Series(solution.x[:len(ids)] if status else [None] * len(ids),
        #                     index=ids)
        weights = pd.Series(solution.x[:len(ids)], index=ids)

        self.results.update({
            'weights': weights.to_dict(),
            'status': status,
        })

        return None

    def model_qpsolvers(self) -> None:

        # constraints
        constraints = self.constraints
        GhAb = constraints.to_GhAb()
        lb = constraints.box['lower'].to_numpy() if constraints.box['box_type'] != 'NA' else None
        ub = constraints.box['upper'].to_numpy() if constraints.box['box_type'] != 'NA' else None
        
        # Solver settings
        solver_settings = dict(self.params)
        if 'solver_name' in solver_settings:
            solver_settings['solver'] = solver_settings.pop('solver_name')

        # Create the optimization model as a QuadraticProgram
        self.model = QuadraticProgram(
            P=self.objective.coefficients['P'],
            q=self.objective.coefficients['q'],
            G=GhAb['G'],
            h=GhAb['h'],
            A=GhAb['A'],
            b=GhAb['b'],
            lb=lb,
            ub=ub,
            **solver_settings
        )

        # Deal with turnover constraint or penalty (cannot have both)
        turnover_penalty = self.params.get('turnover_penalty')

        ## Turnover constraint
        tocon = self.constraints.l1.get('turnover')
        if tocon is not None and (turnover_penalty is None or turnover_penalty == 0):
            x_init = np.array(list(tocon['x0'].values()))
            self.model.linearize_turnover_constraint(x_init=x_init,
                                                     to_budget=tocon['rhs'])

        ## Turnover penalty
        if turnover_penalty is not None and turnover_penalty > 0:
            x_init = pd.Series(self.params.get('x_init')).to_numpy()
            self.model.linearize_turnover_objective(x_init=x_init,
                                                    turnover_penalty=turnover_penalty)

        return None



class EmptyOptimization(Optimization):
    '''
    Placeholder class for an optimization.
    This class is intended to be a placeholder and should not be used directly.
    '''

    def set_objective(self, optimization_data: OptimizationData) -> None:
        raise NotImplementedError(
            'EmptyOptimization is a placeholder and does not implement set_objective.'
        )

    def solve(self) -> None:
        raise NotImplementedError(
            'EmptyOptimization is a placeholder and does not implement solve.'
        )




class LeastSquares(Optimization):

    def __init__(self,
                 constraints: Optional[Constraints] = None,
                 covariance: Optional[Covariance] = None,
                 **kwargs):
        super().__init__(
            constraints=constraints,
            **kwargs
        )
        self.covariance = covariance

    def set_objective(self, optimization_data: OptimizationData) -> None:

        X = optimization_data['return_series']
        y = optimization_data['bm_series']
        if self.params.get('log_transform'):
            X = np.log(1 + X)
            y = np.log(1 + y)

        P = 2 * (X.T @ X)
        q = to_numpy(-2 * X.T @ y).reshape((-1,))
        constant = to_numpy(y.T @ y).item()

        l2_penalty = self.params.get('l2_penalty')
        if l2_penalty is not None and l2_penalty != 0:
            P += 2 * l2_penalty * np.eye(X.shape[1])

        self.objective = Objective(
            P=P,
            q=q,
            constant=constant
        )
        return None

    def solve(self) -> None:
        return super().solve()



class BlackLitterman(Optimization):

    def __init__(self,
                 fields: list[str],
                 covariance: Optional[Covariance] = None,
                 risk_aversion: float = 1,
                 tau_psi: float = 1,
                 tau_omega: float = 1,
                 view_method: str = 'absolute',
                 scalefactor: int = 1,
                 **kwargs) -> None:
        super().__init__(
            fields=fields,
            risk_aversion=risk_aversion,
            tau_psi=tau_psi,
            tau_omega=tau_omega,
            view_method=view_method,
            scalefactor=scalefactor,
            **kwargs
        )
        self.covariance = Covariance() if covariance is None else covariance

    def set_objective(self, optimization_data: OptimizationData) -> None:
        '''
        Sets the objective function for the optimization problem.
        
        Parameters:
        training_data: Training data which must contain 
            return series (to compute the covariances) and scores.
        '''

        # Retrieve configuration parameters from the params attribute
        fields = self.params.get('fields')
        risk_aversion = self.params.get('risk_aversion')
        tau_psi = self.params.get('tau_psi')
        tau_omega = self.params.get('tau_omega')
        view_method = self.params.get('view_method')
        scalefactor = self.params.get('scalefactor')

        # Calculate the covariance matrix
        self.covariance.estimate(
            X=optimization_data['return_series'],
            inplace=True,
        )

        # Extract benchmark weights
        cap_weights = optimization_data['cap_weights']

        # # Alternatively, calculate minimum tracking error portfolio
        # optim = LeastSquares(
        #     constraints = self.constraints,
        #     solver_name = self.params.get('solver_name'),
        # )
        # optim.set_objective(optimization_data=optimization_data)
        # optim.solve()
        # cap_weights = pd.Series(optim.results['weights'])

        # Implied expected return of benchmark
        mu_implied = risk_aversion * self.covariance.matrix @ cap_weights

        # Extract scores
        scores = optimization_data['scores'][fields]

        # Construct the views
        P_tmp = {}
        q_tmp = {}
        for col in scores.columns:
            P_tmp[col], q_tmp[col] = generate_views_from_scores(
                scores=scores[col],
                mu_implied=mu_implied,
                method=view_method,
                scalefactor=scalefactor,
            )

        P = pd.concat(P_tmp, axis=0)
        q = pd.concat(q_tmp, axis=0)

        # Define the uncertainty of the views
        Omega = pd.DataFrame(
            np.diag([tau_omega] * len(q)),
            index=q.index,
            columns=q.index
        )
        Psi = self.covariance.matrix * tau_psi

        # Compute the posterior expected return vector
        mu_posterior = bl_posterior_mean(
            mu_prior=mu_implied,
            P=P,
            q=q,
            Psi=Psi,
            Omega=Omega,
        )

        self.objective = Objective(
            q = mu_posterior * (-1),
            P = self.covariance.matrix * risk_aversion * 2,
        )
        return None

    def solve(self) -> None:
        return super().solve()



class MeanVariance(Optimization):

    def __init__(self,
                 constraints: Optional[Constraints] = None,
                 covariance: Optional[Covariance] = None,
                 expected_return: Optional[ExpectedReturn] = None,
                 risk_aversion: float = 1,
                 **kwargs):
        super().__init__(
            constraints=constraints,
            risk_aversion=risk_aversion,
            **kwargs
        )
        self.covariance = Covariance() if covariance is None else covariance
        self.expected_return = ExpectedReturn() if expected_return is None else expected_return

    def set_objective(self, optimization_data: OptimizationData) -> None:
        X = optimization_data['return_series']
        covmat = self.covariance.estimate(X=X, inplace=False)
        mu = self.expected_return.estimate(X=X, inplace=False)
        self.objective = Objective(
            q = mu * -1,
            P = covmat * 2 * self.params['risk_aversion'],
        )
        return None

    def solve(self) -> None:
        return super().solve()



class MinVariance(Optimization):

    def __init__(self,
                 constraints: Optional[Constraints] = None,
                 covariance: Optional[Covariance] = None,
                 **kwargs):
        super().__init__(
            constraints=constraints,
            **kwargs
        )
        self.covariance = Covariance() if covariance is None else covariance

    def set_objective(self, optimization_data: OptimizationData) -> None:
        X = optimization_data['return_series']
        covmat = self.covariance.estimate(X=X, inplace=False)
        mu = np.zeros(X.shape[1])
        self.objective = Objective(
            q = mu ,
            P = covmat * 2,
        )
        return None

    def solve(self) -> None:
        if self.params.get('solver_name') == 'analytical':
            GhAb = self.constraints.to_GhAb()
            if GhAb['G'] is not None:
                raise ValueError(
                    'Analytical solution does not exist whith inequality constraints.'
                )
            A = GhAb['A']
            b = GhAb['b']
            # If b is scalar, convert it to a 1D array
            if isinstance(b, (int, float)):
                b = np.array([b])
            elif b.ndim == 0:
                b = np.array([b])

            P = self.objective.coefficients['P']
            P_inv = np.linalg.inv(P)

            AP_invA = A @ P_inv @ A.T
            if AP_invA.shape[0] > 1:
                AP_invA_inv = np.linalg.inv(AP_invA)
            else:
                AP_invA_inv = 1 / AP_invA
            x = pd.Series(P_inv @ A.T @ AP_invA_inv @ b,
                          index=self.constraints.ids)      
            self.results.update({
                'weights': x.to_dict(),
                'status': True,
            })
            return None
        else:
            return super().solve()


class ScoreVariance(Optimization):

    def __init__(self,
                 field: str,
                 constraints: Optional[Constraints] = None,
                 covariance: Optional[Covariance] = None,
                 risk_aversion: float = 1,
                 **kwargs):
        super().__init__(
            field=field,
            constraints=constraints,
            risk_aversion=risk_aversion,
            **kwargs,
        )
        self.covariance = Covariance() if covariance is None else covariance

    def set_objective(self, optimization_data: OptimizationData) -> None:

        # Arguments
        risk_aversion = self.params.get('risk_aversion')
        field = self.params.get('field')
        if field is None:
            raise ValueError('Field must be specified.')

        # Extract the scores from the optimization data
        scores = optimization_data['scores'][field]

        # Create quadratic part of the objective function
        # If risk aversion is not None and not equal to 0, use covariance matrix
        if risk_aversion is not None and risk_aversion != 0:
            P = self.covariance.estimate(
                X=optimization_data['return_series'],
                inplace=False
            ) * 2 * risk_aversion
        else:
            P = np.zeros(shape = (len(scores), len(scores)))
        self.objective = Objective(
            q = scores * (-1),
            P = P,
        )

        return None

    def solve(self) -> None:
        return super().solve()
