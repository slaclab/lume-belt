from distgen import Generator
import os


from .run import BELT
from h5py import File
from .evaluate import default_belt_merit
from . import tools
from typing import Optional, Dict, Union, Callable
from .types import AnyPath
import distgen
from .particles import BELTParticleData


def run_belt(
    belt_config: Union[str, Dict],
    settings: Optional[Dict] = None,
    workdir: Optional[AnyPath] = None,
    verbose: bool = False,
):
    """
    Creates, runs, and returns an Impact object using distgen input.

    .distgen_input = parsed distgen.Generatator's .input is attached to the object.

    """

    # setup objects
    if isinstance(belt_config, str):
        E = BELT.from_yaml(belt_config)
    else:
        E = BELT(**belt_config)

    if workdir:
        E._workdir = workdir  # TODO: fix in LUME-Base
        E.configure()  # again

    E.verbose = verbose

    if settings:
        for key in settings:
            
            val = settings[key]

            # reading ImpactT particles
            if key == "Impact_particles": 
                
                if verbose:
                    print(f"Reading {key} = {val}")

                
                E.initial_particles = BELTParticleData.from_ParticleGroup_h5(h5 = val)
            #upsampling particles
            elif key == "num_doublings":
                
                E.initial_particles.upsampling(num_doublings = val)
                
            else:
                # Assume BELT
                if verbose:
                    print(f"Setting BELT {key} = {val}")
                if key.startswith("parameters:"):
                    key = key[len("parameters:") :]
                    setattr(E.input.parameters, key, val)
                elif key == "phase_space_coefficients":
                    E.input.phase_space_coefficients.coefficients = val
                elif key == "current_coefficients":
                    E.input.phase_space_coefficients.coefficients = val
                else:
                    # Assume lattice
                    key = key.split(":")
                    for element in E.input.lattice_lines:
                        if element.name == key[0]:
                            setattr(element, key[1], val)


    # Attach particles
    #E.initial_particles = P

    E.run()

    return E


def evaluate_belt(
    belt_config: Union[str, Dict],
    settings: Optional[Dict],
    workdir: Optional[AnyPath] = None,
    archive_path: Optional[AnyPath] = None,
    merit_f: Optional[Callable] = None,
    verbose: bool = False,
):
    """

    Similar to run_impact_with_distgen, but requires settings a the only positional argument.

    If an archive_path is given, the complete evaluated Impact and Generator objects will be archived
    to a file named using a fingerprint from both objects.

    If merit_f is given, this function will be applied to the evaluated Impact object, and this will be returned.

    Otherwise, a default function will be applied.


    """

    E = run_belt(
        settings=settings,
        belt_config=belt_config,
        workdir=workdir,
        verbose=verbose,
    )

    if merit_f:
        output = merit_f(E)
    else:
        output = default_belt_merit(E)

    if "error" in output and output["error"]:
        raise ValueError("run_impact_with_distgen returned error in output")

    # Recreate Generator object for fingerprint, proper archiving

    fingerprint = fingerprint_belt(E)
    output["fingerprint"] = fingerprint

    if archive_path:
        path = tools.full_path(archive_path)
        assert os.path.exists(path), f"archive path does not exist: {path}"
        archive_file = os.path.join(path, fingerprint + ".h5")
        output["archive"] = archive_file

        # Call the composite archive method
        archive_belt(E, archive_file=archive_file)

    return output


def fingerprint_belt(belt_object: BELT):
    """
    Calls fingerprint() of each of these objects
    """
    f1 = belt_object.fingerprint()
    #f2 = distgen_object.fingerprint()
    d = {"f1": f1}
    return tools.fingerprint(d)


def archive_belt(
    belt_object,
    archive_file=None,
    belt_group="belt",
    
):
    """
    Creates a new archive_file (hdf5) with groups for
    impact and distgen.

    Calls .archive method of Impact and Distgen objects, into these groups.
    """

    h5 = File(archive_file, "w")

    # fingerprint = tools.fingerprint(astra_object.input.update(distgen.input))

    g = h5.create_group(belt_group)
    belt_object.archive(g)

    h5.close()