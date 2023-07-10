#
# Class for particles using the MSMR model
#
import pybamm
from .base_particle import BaseParticle


class MSMRDiffusion(BaseParticle):
    """
    Class for molar conservation in particles within the Multi-Species Multi-Reaction
    framework :footcite:t:`Baker2018`.

    Parameters
    ----------
    param : parameter class
        The parameters to use for this submodel
    domain : str
        The domain of the model either 'Negative' or 'Positive'
    options: dict
        A dictionary of options to be passed to the model.
        See :class:`pybamm.BaseBatteryModel`
    phase : str, optional
        Phase of the particle (default is "primary")
    x_average : bool
        Whether the particle concentration is averaged over the x-direction
    """

    def __init__(self, param, domain, options, phase="primary", x_average=False):
        super().__init__(param, domain, options, phase)
        self.x_average = x_average

        pybamm.citations.register("Baker2018")

    def get_fundamental_variables(self):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        variables = {}

        # Define "particle" potential variables. In the MSMR model, we solve for the
        # potential as a function of position within the electrode and particles (and
        # particle-size distribution, if applicable). The potential is then used to
        # calculate the stoichiometry, which is used to calculate the particle
        # concentration.
        c_max = self.phase_param.c_max
        if self.size_distribution is False:
            if self.x_average is False:
                U = pybamm.Variable(
                    f"{Domain} {phase_name}particle potential [V]",
                    f"{domain} {phase_name}particle",
                    auxiliary_domains={
                        "secondary": f"{domain} electrode",
                        "tertiary": "current collector",
                    },
                )
                U.print_name = f"U_{domain[0]}"
            else:
                U_xav = pybamm.Variable(
                    f"X-averaged {domain} {phase_name}particle " "potential [V]",
                    f"{domain} {phase_name}particle",
                    auxiliary_domains={"secondary": "current collector"},
                )
                U_xav.print_name = f"U_{domain[0]}_xav"
                U = pybamm.SecondaryBroadcast(U_xav, f"{domain} electrode")
        else:
            if self.x_average is False:
                U_distribution = pybamm.Variable(
                    f"{Domain} {phase_name}particle " "potential distribution [V]",
                    domain=f"{domain} {phase_name}particle",
                    auxiliary_domains={
                        "secondary": f"{domain} {phase_name}particle size",
                        "tertiary": f"{domain} electrode",
                        "quaternary": "current collector",
                    },
                )
                R = pybamm.SpatialVariable(
                    f"R_{domain[0]}",
                    domain=[f"{domain} {phase_name}particle size"],
                    auxiliary_domains={
                        "secondary": f"{domain} electrode",
                        "tertiary": "current collector",
                    },
                    coord_sys="cartesian",
                )
                variables = self._get_distribution_variables(R)
                f_v_dist = variables[
                    f"{Domain} volume-weighted {phase_name}"
                    "particle-size distribution [m-1]"
                ]
            else:
                U_distribution = pybamm.Variable(
                    f"X-averaged {domain} {phase_name}particle "
                    "potential distribution [V]",
                    domain=f"{domain} {phase_name}particle",
                    auxiliary_domains={
                        "secondary": f"{domain} {phase_name}particle size",
                        "tertiary": "current collector",
                    },
                )
                R = pybamm.SpatialVariable(
                    f"R_{domain[0]}",
                    domain=[f"{domain} {phase_name}particle size"],
                    auxiliary_domains={"secondary": "current collector"},
                    coord_sys="cartesian",
                )
                variables = self._get_distribution_variables(R)
                f_v_dist = variables[
                    f"X-averaged {domain} volume-weighted {phase_name}"
                    "particle-size distribution [m-1]"
                ]

            # Standard potential distribution_variables
            variables.update(
                self._get_standard_potential_distribution_variables(U_distribution)
            )

            # Calculate the stoichiometry distribution from the potential distribution
            X_distribution = self.phase_param.X(U_distribution)
            dXdU_distribution = self.phase_param.dXdU(U_distribution)

            # Standard stoichiometry and concentration distribution variables
            # (size-dependent)
            c_s_distribution = X_distribution * c_max
            variables.update(
                self._get_standard_concentration_distribution_variables(
                    c_s_distribution
                )
            )
            variables.update(
                self._get_standard_differential_stoichiometry_distribution_variables(
                    dXdU_distribution
                )
            )

            # Standard size-averaged variables. Average potentials using
            # the volume-weighted distribution since they are volume-based
            # quantities. Necessary for output variables "Total lithium in
            # negative electrode [mol]", etc, to be calculated correctly
            U = pybamm.Integral(f_v_dist * U_distribution, R)
            if self.x_average is True:
                U = pybamm.SecondaryBroadcast(U, [f"{domain} electrode"])

        # Standard potential variables
        variables.update(self._get_standard_potential_variables(U))

        # Calculate the stoichiometry from the potential
        X = self.phase_param.X(U)
        dXdU = self.phase_param.dXdU(U)

        # Standard stoichiometry and concentration variables (size-independent)
        c_s = X * c_max
        variables.update(self._get_standard_concentration_variables(c_s))
        variables.update(self._get_standard_differential_stoichiometry_variables(dXdU))

        return variables

    def get_coupled_variables(self, variables):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name
        param = self.param

        if self.size_distribution is False:
            if self.x_average is False:
                X = variables[f"{Domain} {phase_name}particle stoichiometry"]
                dXdU = variables[
                    f"{Domain} {phase_name}particle differential stoichiometry [V-1]"
                ]
                U = variables[f"{Domain} {phase_name}particle potential [V]"]
                T = pybamm.PrimaryBroadcast(
                    variables[f"{Domain} electrode temperature [K]"],
                    [f"{domain} {phase_name}particle"],
                )
                R_nondim = variables[f"{Domain} {phase_name}particle radius"]
                j = variables[
                    f"{Domain} electrode {phase_name}"
                    "interfacial current density [A.m-2]"
                ]
            else:
                X = variables[f"X-averaged {domain} {phase_name}particle stoichiometry"]
                dXdU = variables[
                    f"X-averaged {domain} {phase_name}particle differential "
                    "stoichiometry [V-1]"
                ]
                U = variables[
                    f"X-averaged {domain} {phase_name}particle " "potential [V]"
                ]
                T = pybamm.PrimaryBroadcast(
                    variables[f"X-averaged {domain} electrode temperature [K]"],
                    [f"{domain} {phase_name}particle"],
                )
                R_nondim = 1
                j = variables[
                    f"X-averaged {domain} electrode {phase_name}"
                    "interfacial current density [A.m-2]"
                ]
            R_broad_nondim = R_nondim
        else:
            R_nondim = variables[f"{Domain} {phase_name}particle sizes"]
            R_broad_nondim = pybamm.PrimaryBroadcast(
                R_nondim, [f"{domain} {phase_name}particle"]
            )
            if self.x_average is False:
                X = variables[
                    f"{Domain} {phase_name}particle stoichiometry distribution"
                ]
                dXdU = variables[
                    f"{Domain} {phase_name}particle differential stoichiometry "
                    "distribution [V-1]"
                ]
                U = variables[
                    f"{Domain} {phase_name}particle potential " "distribution [V]"
                ]
                # broadcast T to "particle size" domain then again into "particle"
                T = pybamm.PrimaryBroadcast(
                    variables[f"{Domain} electrode temperature [K]"],
                    [f"{domain} {phase_name}particle size"],
                )
                T = pybamm.PrimaryBroadcast(T, [f"{domain} {phase_name}particle"])
                j = variables[
                    f"{Domain} electrode {phase_name}interfacial "
                    "current density distribution [A.m-2]"
                ]
            else:
                X = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "stoichiometry distribution"
                ]
                dXdU = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "differential stoichiometry distribution [V-1]"
                ]
                U = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "potential distribution [V]"
                ]
                # broadcast to "particle size" domain then again into "particle"
                T = pybamm.PrimaryBroadcast(
                    variables[f"X-averaged {domain} electrode temperature [K]"],
                    [f"{domain} {phase_name}particle size"],
                )
                T = pybamm.PrimaryBroadcast(T, [f"{domain} {phase_name}particle"])
                j = variables[
                    f"X-averaged {domain} electrode {phase_name}interfacial "
                    "current density distribution [A.m-2]"
                ]

        # Note: diffusivity is given as a function of concentration here,
        # not stoichiometry
        c_max = self.phase_param.c_max
        D_eff = self._get_effective_diffusivity(X * c_max, T)
        f = self.param.F / (self.param.R * T)
        N_s = c_max * X * (1 - X) * f * D_eff * pybamm.grad(U)
        variables.update(
            {
                f"{Domain} {phase_name}particle rhs [V.s-1]": -(
                    1 / (R_broad_nondim**2)
                )
                * pybamm.div(N_s)
                / c_max
                / dXdU,
                f"{Domain} {phase_name}particle bc [V.m-1]": j
                * R_nondim
                / param.F
                / pybamm.surf(c_max * X * (1 - X) * f * D_eff),
            }
        )

        if self.size_distribution is True:
            # Size-dependent flux variables
            variables.update(
                self._get_standard_diffusivity_distribution_variables(D_eff)
            )
            variables.update(self._get_standard_flux_distribution_variables(N_s))
            # Size-averaged flux variables
            R = variables[f"{Domain} {phase_name}particle sizes [m]"]
            f_a_dist = self.phase_param.f_a_dist(R)
            D_eff = pybamm.Integral(f_a_dist * D_eff, R)
            N_s = pybamm.Integral(f_a_dist * N_s, R)

        if self.x_average is True:
            D_eff = pybamm.SecondaryBroadcast(D_eff, [f"{domain} electrode"])
            N_s = pybamm.SecondaryBroadcast(N_s, [f"{domain} electrode"])

        variables.update(self._get_standard_diffusivity_variables(D_eff))
        variables.update(self._get_standard_flux_variables(N_s))

        return variables

    def set_rhs(self, variables):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        if self.size_distribution is False:
            if self.x_average is False:
                U = variables[f"{Domain} {phase_name}particle potential [V]"]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle " "potential [V]"
                ]
        else:
            if self.x_average is False:
                U = variables[
                    f"{Domain} {phase_name}particle " "potential distribution [V]"
                ]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "potential distribution [V]"
                ]
        self.rhs = {U: variables[f"{Domain} {phase_name}particle rhs [V.s-1]"]}

    def set_boundary_conditions(self, variables):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        if self.size_distribution is False:
            if self.x_average is False:
                U = variables[f"{Domain} {phase_name}particle potential [V]"]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle " "potential [V]"
                ]
        else:
            if self.x_average is False:
                U = variables[
                    f"{Domain} {phase_name}particle " "potential distribution [V]"
                ]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "potential distribution [V]"
                ]

        rbc = variables[f"{Domain} {phase_name}particle bc [V.m-1]"]
        self.boundary_conditions = {
            U: {"left": (pybamm.Scalar(0), "Neumann"), "right": (rbc, "Neumann")}
        }

    def set_initial_conditions(self, variables):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        U_init = self.phase_param.U_init
        if self.size_distribution is False:
            if self.x_average is False:
                U = variables[f"{Domain} {phase_name}particle potential [V]"]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle " "potential [V]"
                ]
        else:
            if self.x_average is False:
                U = variables[
                    f"{Domain} {phase_name}particle " "potential distribution [V]"
                ]
            else:
                U = variables[
                    f"X-averaged {domain} {phase_name}particle "
                    "potential distribution [V]"
                ]
        self.initial_conditions = {U: U_init}

    def _get_standard_potential_variables(self, U):
        """
        A private function to obtain the standard variables which can be derived from
        the potential.
        """
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name
        U_surf = pybamm.surf(U)
        U_surf_av = pybamm.x_average(U_surf)
        U_xav = pybamm.x_average(U)
        U_rav = pybamm.r_average(U)
        U_av = pybamm.r_average(U_xav)
        variables = {
            f"{Domain} {phase_name}particle potential [V]": U,
            f"X-averaged {domain} {phase_name}particle " "potential [V]": U_xav,
            f"R-averaged {domain} {phase_name}particle " "potential [V]": U_rav,
            f"Average {domain} {phase_name}particle potential [V]": U_av,
            f"{Domain} {phase_name}particle surface potential [V]": U_surf,
            f"X-averaged {domain} {phase_name}particle "
            "surface potential [V]": U_surf_av,
            f"Minimum {domain} {phase_name}particle potential [V]" "": pybamm.min(U),
            f"Maximum {domain} {phase_name}particle potential [V]" "": pybamm.max(U),
            f"Minimum {domain} {phase_name}particle "
            f"Minimum {domain} {phase_name}particle "
            "surface potential [V]": pybamm.min(U_surf),
            f"Maximum {domain} {phase_name}particle "
            "surface potential [V]": pybamm.max(U_surf),
        }
        return variables

    def _get_standard_potential_distribution_variables(self, U):
        """
        A private function to obtain the standard variables which can be derived from
        the potential distribution in particle size.
        """
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        # Broadcast and x-average when necessary
        if U.domain == [f"{domain} {phase_name}particle size"] and U.domains[
            "secondary"
        ] != [f"{domain} electrode"]:
            # X-avg potential distribution
            U_xav_distribution = pybamm.PrimaryBroadcast(
                U, [f"{domain} {phase_name}particle"]
            )

            # Surface potential distribution variables
            U_surf_xav_distribution = U
            U_surf_distribution = pybamm.SecondaryBroadcast(
                U_surf_xav_distribution, [f"{domain} electrode"]
            )

            # potential distribution in all domains.
            U_distribution = pybamm.PrimaryBroadcast(
                U_surf_distribution, [f"{domain} {phase_name}particle"]
            )
        elif U.domain == [f"{domain} {phase_name}particle"] and (
            U.domains["tertiary"] != [f"{domain} electrode"]
        ):
            # X-avg potential distribution
            U_xav_distribution = U

            # Surface potential distribution variables
            U_surf_xav_distribution = pybamm.surf(U_xav_distribution)
            U_surf_distribution = pybamm.SecondaryBroadcast(
                U_surf_xav_distribution, [f"{domain} electrode"]
            )

            # potential distribution in all domains
            U_distribution = pybamm.TertiaryBroadcast(
                U_xav_distribution, [f"{domain} electrode"]
            )
        elif U.domain == [f"{domain} {phase_name}particle size"] and U.domains[
            "secondary"
        ] == [f"{domain} electrode"]:
            # Surface potential distribution variables
            U_surf_distribution = U
            U_surf_xav_distribution = pybamm.x_average(U)

            # X-avg potential distribution
            U_xav_distribution = pybamm.PrimaryBroadcast(
                U_surf_xav_distribution, [f"{domain} {phase_name}particle"]
            )

            # potential distribution in all domains
            U_distribution = pybamm.PrimaryBroadcast(
                U_surf_distribution, [f"{domain} {phase_name}particle"]
            )
        else:
            U_distribution = U

            # x-average the *tertiary* domain.
            # NOTE: not yet implemented. Make 0.5 everywhere
            U_xav_distribution = pybamm.FullBroadcast(
                0.5,
                [f"{domain} {phase_name}particle"],
                {
                    "secondary": f"{domain} {phase_name}particle size",
                    "tertiary": "current collector",
                },
            )

            # Surface potential distribution variables
            U_surf_distribution = pybamm.surf(U)
            U_surf_xav_distribution = pybamm.x_average(U_surf_distribution)

        U_rav_distribution = pybamm.r_average(U_distribution)
        U_av_distribution = pybamm.x_average(U_rav_distribution)

        variables = {
            f"{Domain} {phase_name}particle potential distribution [V]": U_distribution,
            f"X-averaged {domain} {phase_name}particle potential "
            "distribution [V]": U_xav_distribution,
            f"R-averaged {domain} {phase_name}particle potential "
            "distribution [V]": U_rav_distribution,
            f"Average {domain} {phase_name}particle potential "
            "distribution [V]": U_av_distribution,
            f"{Domain} {phase_name}particle surface potential"
            " distribution [V]": U_surf_distribution,
            f"X-averaged {domain} {phase_name}particle surface potential "
            "distribution [V]": U_surf_xav_distribution,
        }
        return variables

    def _get_standard_differential_stoichiometry_variables(self, dXdU):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        dXdU_surf = pybamm.surf(dXdU)
        dXdU_surf_av = pybamm.x_average(dXdU_surf)
        dXdU_xav = pybamm.x_average(dXdU)
        dXdU_rav = pybamm.r_average(dXdU)
        dXdU_av = pybamm.r_average(dXdU_xav)

        variables = {
            f"{Domain} {phase_name}particle differential stoichiometry [V-1]": dXdU,
            f"X-averaged {domain} {phase_name}particle "
            "differential stoichiometry [V-1]": dXdU_xav,
            f"R-averaged {domain} {phase_name}particle "
            "differential stoichiometry [V-1]": dXdU_rav,
            f"Average {domain} {phase_name}particle differential "
            "stoichiometry [V-1]": dXdU_av,
            f"{Domain} {phase_name}particle surface differential "
            "stoichiometry [V-1]": dXdU_surf,
            f"X-averaged {domain} {phase_name}particle "
            "surface differential stoichiometry [V-1]": dXdU_surf_av,
        }

        return variables

    def _get_standard_differential_stoichiometry_distribution_variables(self, dXdU):
        domain, Domain = self.domain_Domain
        phase_name = self.phase_name

        # Broadcast and x-average when necessary
        if dXdU.domain == [f"{domain} {phase_name}particle size"] and dXdU.domains[
            "secondary"
        ] != [f"{domain} electrode"]:
            # X-avg differential stoichiometry distribution
            dXdU_xav_distribution = pybamm.PrimaryBroadcast(
                dXdU, [f"{domain} {phase_name}particle"]
            )

            # Surface differential stoichiometry distribution variables
            dXdU_surf_xav_distribution = dXdU
            dXdU_surf_distribution = pybamm.SecondaryBroadcast(
                dXdU_surf_xav_distribution, [f"{domain} electrode"]
            )

            # Differential stoichiometry distribution in all domains.
            dXdU_distribution = pybamm.PrimaryBroadcast(
                dXdU_surf_distribution, [f"{domain} {phase_name}particle"]
            )
        elif dXdU.domain == [f"{domain} {phase_name}particle"] and (
            dXdU.domains["tertiary"] != [f"{domain} electrode"]
        ):
            # X-avg differential stoichiometry distribution
            dXdU_xav_distribution = dXdU

            # Surface differential stoichiometry distribution variables
            dXdU_surf_xav_distribution = pybamm.surf(dXdU_xav_distribution)
            dXdU_surf_distribution = pybamm.SecondaryBroadcast(
                dXdU_surf_xav_distribution, [f"{domain} electrode"]
            )

            # Differential stoichiometry distribution in all domains.
            dXdU_distribution = pybamm.TertiaryBroadcast(
                dXdU_xav_distribution, [f"{domain} electrode"]
            )
        elif dXdU.domain == [f"{domain} {phase_name}particle size"] and dXdU.domains[
            "secondary"
        ] == [f"{domain} electrode"]:
            # Surface differential stoichiometry distribution variables
            dXdU_surf_distribution = dXdU
            dXdU_surf_xav_distribution = pybamm.x_average(dXdU)

            # X-avg differential stoichiometry distribution
            dXdU_xav_distribution = pybamm.PrimaryBroadcast(
                dXdU_surf_xav_distribution, [f"{domain} {phase_name}particle"]
            )

            # Differential stoichiometry distribution in all domains
            dXdU_distribution = pybamm.PrimaryBroadcast(
                dXdU_surf_distribution, [f"{domain} {phase_name}particle"]
            )
        else:
            dXdU_distribution = dXdU

            # x-average the *tertiary* domain.
            # NOTE: not yet implemented. Make 0.5 everywhere
            dXdU_xav_distribution = pybamm.FullBroadcast(
                0.5,
                [f"{domain} {phase_name}particle"],
                {
                    "secondary": f"{domain} {phase_name}particle size",
                    "tertiary": "current collector",
                },
            )

            # Surface differential stoichiometry distribution variables
            dXdU_surf_distribution = pybamm.surf(dXdU)
            dXdU_surf_xav_distribution = pybamm.x_average(dXdU_surf_distribution)

        dXdU_rav_distribution = pybamm.r_average(dXdU_distribution)
        dXdU_av_distribution = pybamm.x_average(dXdU_rav_distribution)

        variables = {
            f"{Domain} {phase_name}particle differential stoichiometry distribution "
            "[V-1]": dXdU_distribution,
            f"X-averaged {domain} {phase_name}particle differential stoichiometry "
            "distribution [V-1]": dXdU_xav_distribution,
            f"R-averaged {domain} {phase_name}particle differential stoichiometry "
            "distribution [V-1]": dXdU_rav_distribution,
            f"Average {domain} {phase_name}particle differential stoichiometry "
            "distribution [V-1]": dXdU_av_distribution,
            f"{Domain} {phase_name}particle surface differential stoichiometry"
            " distribution [V-1]": dXdU_surf_distribution,
            f"X-averaged {domain} {phase_name}particle surface differential "
            "stoichiometry distribution [V-1]": dXdU_surf_xav_distribution,
        }
        return variables