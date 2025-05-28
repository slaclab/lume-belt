from pydantic import BaseModel
from pydantic import Field
from .types import AnyPath, NDArray
from pmd_beamphysics import ParticleGroup
from pmd_beamphysics.interfaces.impact import impact_particles_to_particle_data
import numpy as np
from pmd_beamphysics.units import mec2, c_light
import os
from typing import Optional


def parse_impact_particles(
    filePath, names=("x", "GBx", "y", "GBy", "z", "GBz"), skiprows=0
):
    """
    Parse Impact-T input and output particle data.
    Typical filenames: 'partcl.data', 'fort.40', 'fort.50'.

    Note that partcl.data has the number of particles in the first line, so skiprows=1 should be used.

    Returns a structured numpy array

    Impact-T input/output particles distribions are ASCII files with columns:
    x (m)
    GBy = gamma*beta_x (dimensionless)
    y (m)
    GBy = gamma*beta_y (dimensionless)
    z (m)
    GBz = gamma*beta_z (dimensionless)

    """

    dtype = {"names": names, "formats": 6 * [float]}
    pdat = np.loadtxt(
        filePath, skiprows=skiprows, dtype=dtype, ndmin=1
    )  # to make sure that 1 particle is parsed the same as many.

    return pdat


# Function to increase the number of particles by successive doubling
def upsample_particles(input_particles, num_doublings, num_bins=200):
    #np.random.seed(42)  # For reproducibility
    if num_doublings == 0:
        return input_particles

    else:    
        particles = input_particles.copy()
        particles = particles[particles[:, 0].argsort()]
   
        new_particles = []
        for i in range(len(particles) - 1):
            # Insert new particle "near" each pair in time
            t_new = (particles[i, 0] + particles[i + 1, 0]) / 2  # Midpoint in time
            p_new = particles[i, 1]  # Use p from one of the original particles
            new_particles.append([t_new, p_new])
        particles = np.vstack([particles, new_particles])

        # Bin the particles by t into a large number of bins
        t_bins = np.linspace(particles[:, 0].min(), particles[:, 0].max(), num_bins + 1)
        digitized = np.digitize(particles[:, 0], bins=t_bins)

        randomized_particles = []
        for bin_idx in range(1, len(t_bins)):
            bin_mask = digitized == bin_idx
            bin_particles = particles[bin_mask]

            if len(bin_particles) > 1:
                # Randomize p values within the bin and add small noise
                randomized_p = np.random.permutation(bin_particles[:, 1]) + np.std(bin_particles[:, 1])*np.random.normal(0, 0.05, len(bin_particles))
                randomized_bin_particles = np.column_stack((bin_particles[:, 0], randomized_p))
                randomized_particles.append(randomized_bin_particles)
            else:
                randomized_particles.append(bin_particles)

        randomized_particles = np.vstack(randomized_particles)
        return upsample_particles(randomized_particles, num_doublings - 1, num_bins)

class BELTParticleData(BaseModel):
    """ """

    z: NDArray = Field(..., description="Z coordinate (m)")
    delta_gamma: NDArray = Field(..., description="Δγ")
    weight: NDArray = Field(..., description="Particle weight")
    delta_e_over_e0: NDArray = Field(..., description="dE/E0")
    Ek: Optional[float] = Field(None, description="Electron reference energy")
    np: int = Field(..., description="Number of macroparticles")
    beam_radius: Optional[float] = None

    @classmethod
    def from_ParticleGroup(cls, pg: ParticleGroup) -> "BELTParticleData":
       # if not Ek:
        Ek = pg["mean_kinetic_energy"]
        return cls(
            z=pg.z - np.mean(pg.z),
            delta_gamma=pg.gamma - Ek / mec2,
            delta_e_over_e0=(pg["energy"] - Ek) / Ek,
            weight=pg.weight,
            Ek=Ek,
            beam_radius=np.sqrt(pg["sigma_x"] ** 2 + pg["sigma_y"] ** 2),
            np=len(pg.z),
        )

    @classmethod
    def from_ParticleGroup_h5(cls, h5: ParticleGroup) -> "BELTParticleData":
        pg = ParticleGroup(h5)
        return cls.from_ParticleGroup(pg)
        
    @classmethod
    def from_BELT_outputfile(
        cls, filepath: AnyPath, 
    ) -> "BELTParticleData":
        data = np.loadtxt(filepath)
        data = np.atleast_2d(data)  # Ensure the data is always a 2D array

        # Update delta_gamma and delta_e_over_e0 given the new Ek

        output = cls(  
            z=data[:, 0],
            delta_gamma=data[:, 1],
            weight=data[:, 2],
            delta_e_over_e0=data[:, 3],
            np=data.shape[0],
            Ek = np.mean(data[:, 1] / data[:, 3])*mec2
        )

        #if Ek:
        #    output.shift_ref_energy(Ek)

        return output

#    def shift_ref_energy(self, Ek: float) -> None:
#        print("Shifting delta_e_over_e0 and delta_gamma given Ek")
#        self.delta_gamma = self.gamma - Ek / mec2
#        self.delta_e_over_e0 = self.delta_gamma / (Ek / mec2)
#        self.Ek = Ek

    @classmethod
    def from_ImpactT_outputfile(
        cls, path: AnyPath,  mc2: float = mec2, species: str = "electron"
    ) -> "BELTParticleData":
        tout = parse_impact_particles(path)
        data = impact_particles_to_particle_data(tout, mc2, species)
        pg = ParticleGroup(data=data)
        Ek = pg["mean_kinetic_energy"]
        return cls.from_ParticleGroup(pg)

    def to_particlegroup(self) -> ParticleGroup:
        z = self.z
        gamma = self.gamma
        weight = self.weight
        n = len(z)
        pz = np.sqrt(gamma**2 - 1) * mec2
        particlegroup_data = dict(
            t=self.z / c_light,
            x=np.zeros(n),
            px=np.zeros(n),
            y=np.zeros(n),
            py=np.zeros(n),
            z=self.z,
            pz=pz,
            weight=weight,
            status=np.ones(n),
            species="electron",
        )
        return ParticleGroup(data=particlegroup_data)

    def upsampling(self, num_doublings: int, num_bins: Optional[int]=100):
        orig_particle = np.vstack((self.z, self.delta_gamma)).T
        new_particle = upsample_particles(orig_particle, num_doublings, num_bins)
        
        print("Upsampling the particle number to ", new_particle.shape[0])

        self.z = new_particle[:,0]
        self.delta_gamma = new_particle[:,1]
        self.np = new_particle.shape[0]
        self.weight = np.sum(self.weight)/new_particle.shape[0]*np.ones(self.z.shape)
        self.delta_e_over_e0 = self.delta_gamma*mec2/self.Ek
        
        

    def plot(self, xkey: str, ykey: str, bins: int = 50) -> None:
        return self.to_particlegroup().plot(xkey, ykey, bins=bins, return_figure=True)

    def write_BELT_input(self, path: AnyPath, verbose: bool = True) -> None:
        data = np.vstack(
            (self.z, self.delta_gamma, self.weight, self.delta_e_over_e0)
        ).T
        file_path = os.path.join(path, "pts.in")
        np.savetxt(file_path, data)

    @property
    def gamma0(self):
        return self.delta_gamma / self.delta_e_over_e0

    @property
    def gamma(self):
        return self.gamma0 + self.delta_gamma

    @property 
    def charge(self):
        return np.sum(self.weight)


# class ImactTSliceData(BaseModel):
#    pass
