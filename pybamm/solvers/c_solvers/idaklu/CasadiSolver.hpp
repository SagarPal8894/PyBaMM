#ifndef PYBAMM_IDAKLU_CASADI_SOLVER_HPP
#define PYBAMM_IDAKLU_CASADI_SOLVER_HPP

#include <casadi/casadi.hpp>
using Function = casadi::Function;

#include "casadi_functions.hpp"
#include "common.hpp"
#include "options.hpp"
#include "solution.hpp"
#include "sundials_legacy_wrapper.hpp"

/**
 * Abstract base class for solutions that can use different solvers and vector
 * implementations.
 * @brief An abstract base class for the Idaklu solver
 */
class CasadiSolver
{
public:

  /**
   * @brief Default constructor
   */
  CasadiSolver() = default;

  /**
   * @brief Default destructor
   */
  ~CasadiSolver() = default;

  /**
   * @brief Abstract solver method that returns a Solution class
   */
  virtual void solve(
    const realtype *t,
    const int number_of_timesteps,
    const realtype *y0,
    const realtype *yp0,
    const realtype *inputs,
    const int length_of_return_vector,
    realtype *y_return,
    realtype *yS_return,
    realtype *t_return,
    int &t_i,
    int &retval
  ) = 0;

  /**
   * Abstract method to initialize the solver, once vectors and solver classes
   * are set
   * @brief Abstract initialization method
   */
  virtual void Initialize() = 0;
};

#endif // PYBAMM_IDAKLU_CASADI_SOLVER_HPP
