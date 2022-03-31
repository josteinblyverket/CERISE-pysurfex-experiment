import surfex
import os
import json
import numpy as np
import yaml
from datetime import timedelta, datetime
import shutil
import time


class AbstractTask(object):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):

        # TODO
        debug = False
        if "debug" in kwargs:
            debug = kwargs["debug"]

        if surfex is None:
            raise Exception("Surfex module not properly loaded!")

        self.dtg = datetime.strptime(progress["DTG"], "%Y%m%d%H")
        self.dtgbeg = datetime.strptime(progress["DTGBEG"], "%Y%m%d%H")

        self.exp_file_paths = surfex.SystemFilePaths(exp_file_paths)
        self.wd = self.exp_file_paths.get_system_path("exp_dir")

        self.mbr = None
        if "mbr" in kwargs:
            self.mbr = kwargs["mbr"]

        if debug:
            print(config)
            print("        config: ", json.dumps(config, sort_keys=True, indent=2))
            print("        system: ", json.dumps(system, sort_keys=True, indent=2))
            print("exp_file_paths: ", json.dumps(self.exp_file_paths.system_file_paths, sort_keys=True, indent=2))
            print("        kwargs: ", kwargs)

        # Domain/geo
        self.config = surfex.ConfigurationFromJson(config.copy())
        domain = self.config.get_setting("GEOMETRY#DOMAIN", mbr=self.mbr)
        domains = self.wd + "/config/domains/Harmonie_domains.json"
        domains = json.load(open(domains, "r"))
        domain_json = surfex.set_domain(domains, domain, hm_mode=True)
        geo = surfex.get_geo_object(domain_json, debug=debug)
        self.config.settings["GEOMETRY"].update({"GEO": geo})
        self.geo = geo

        self.task = task
        self.task_settings = None

        if kwargs is not None and "task_settings" in kwargs:
            self.task_settings = kwargs["task_settings"]

        self.stream = None
        if "stream" in kwargs:
            self.stream = kwargs["stream"]

        args = None
        if "args" in kwargs:
            iargs = kwargs["args"]
            if iargs != "" and iargs is not None:
                args = {}
                iargs = iargs.split(" ")
                for a in iargs:
                    var = str(a).split("=")
                    key = var[0]
                    value = var[1]
                    args.update({key: value})
        self.args = args

        masterodb = False
        lfagmap = self.config.get_setting("SURFEX#IO#LFAGMAP", mbr=self.mbr)
        self.csurf_filetype = self.config.get_setting("SURFEX#IO#CSURF_FILETYPE", mbr=self.mbr)
        self.suffix = surfex.SurfFileTypeExtension(self.csurf_filetype, lfagmap=lfagmap, masterodb=masterodb).suffix

        self.wrk = self.exp_file_paths.get_system_path("wrk_dir", default_dir="default_wrk_dir", mbr=self.mbr,
                                                       basedtg=self.dtg)
        self.archive = self.exp_file_paths.get_system_path("archive_dir", default_dir="default_archive_dir",
                                                           mbr=self.mbr, basedtg=self.dtg)
        os.makedirs(self.archive, exist_ok=True)
        self.bindir = self.exp_file_paths.get_system_path("bin_dir", default_dir="default_bin_dir")

        self.extrarch = self.exp_file_paths.get_system_path("extrarch_dir", default_dir="default_extrarch_dir",
                                                            mbr=self.mbr,  basedtg=self.dtg)
        os.makedirs(self.extrarch, exist_ok=True)
        self.obsdir = self.exp_file_paths.get_system_path("obs_dir", default_dir="default_obs_dir", mbr=self.mbr,
                                                          basedtg=self.dtg)

        self.exp_file_paths.add_system_file_path("wrk_dir", self.wrk)
        self.exp_file_paths.add_system_file_path("bin_dir", self.bindir)
        self.exp_file_paths.add_system_file_path("archive_dir", self.archive)
        self.exp_file_paths.add_system_file_path("extrarch_dir", self.extrarch)
        self.exp_file_paths.add_system_file_path("obs_dir", self.obsdir)

        os.makedirs(self.obsdir, exist_ok=True)
        self.wdir = str(os.getpid())
        self.wdir = self.wrk + "/" + self.wdir
        print("WDIR=" + self.wdir)
        os.makedirs(self.wdir, exist_ok=True)
        os.chdir(self.wdir)

        hh = self.dtg.strftime("%H")
        self.fcint = self.config.get_fcint(hh, mbr=self.mbr)
        self.fg_dtg = self.dtg - timedelta(hours=self.fcint)
        self.next_dtg = self.dtg + timedelta(hours=self.fcint)
        self.next_dtgpp = self.next_dtg
        self.input_path = self.wd + "/nam"

        self.fg_guess_sfx = self.wrk + "/first_guess_sfx"
        self.fc_start_sfx = self.wrk + "/fc_start_sfx"

        self.translation = {
            "t2m": "air_temperature_2m",
            "rh2m": "relative_humidity_2m",
            "sd": "surface_snow_thickness"
        }
        self.sfx_exp_vars = {}
        self.system = system
        if self.system is not None:
            for key in self.system:
                value = self.system[key]
                self.sfx_exp_vars.update({key: value})

    def run(self, **kwargs):
        # self.prepare(**kwargs)
        # Add system variables to arguments
        if self.sfx_exp_vars is not None:
            kwargs.update({"sfx_exp_vars": self.sfx_exp_vars})
        self.execute(**kwargs)
        self.postfix(**kwargs)

    def execute(self, **kwargs):
        print("WARNING: Using empty base class execute " + str(kwargs))

    def postfix(self, **kwargs):
        print("Base class postfix " + str(kwargs))
        if self.wrk is not None:
            os.chdir(self.wrk)

        if self.wdir is not None:
            shutil.rmtree(self.wdir)


class Dummy(object):

    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        self.task = task
        print("Dummy task initialized: ", task)
        print("        Config: ", json.dumps(config, sort_keys=True, indent=2))
        print("        system: ", json.dumps(system, sort_keys=True, indent=2))
        print("exp_file_paths: ", json.dumps(exp_file_paths, sort_keys=True, indent=2))
        print("      progress: ", json.dumps(progress, sort_keys=True, indent=2))
        print("        kwargs: ", kwargs)

    def run(self, **kwargs):
        print("Dummy task ", self.task, "is run: ", kwargs)


class PrepareCycle(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def run(self, **kwargs):
        self.execute(**kwargs)

    def execute(self, **kwargs):
        if os.path.exists(self.wrk):
            shutil.rmtree(self.wrk)


class QualityControl(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        an_time = self.dtg
        # archive_root = self.get_setting("archive_root")
        settings_var = {
          "t2m": {
            "sets": {
              "netatmo": {
                "varname": "Temperature",
                "filetype": "netatmo",
                "tests": {
                  "nometa": {
                    "do_test": True
                  },
                  "domain": {
                    "do_test": True
                  },
                  "blacklist": {
                    "do_test": True
                  },
                  "redundancy": {
                    "do_test": True
                  },
                  "plausibility": {
                    "do_test": True,
                    "maxval": 340,
                    "minval": 200
                  }
                }
              }
            }
          },
          "rh2m": {
            "sets": {
              "netatmo": {
                "varname": "Humidity",
                "filetype": "netatmo",
                "tests": {
                  "nometa": {
                    "do_test": True
                  },
                  "domain": {
                    "do_test": True
                  },
                  "blacklist": {
                    "do_test": True
                  },
                  "redundancy": {
                    "do_test": True
                  },
                  "plausibility": {
                    "do_test": True,
                    "minval": 0,
                    "maxval": 100
                  }
                }
              }
            }
          },
          "sd": {
            "sets": {
              "bufr": {
                "filetype": "bufr",
                "varname": "totalSnowDepth",
                "tests": {
                  "nometa": {
                    "do_test": True
                  },
                  "domain": {
                    "do_test": True
                  },
                  "blacklist": {
                    "do_test": True
                  },
                  "redundancy": {
                    "do_test": True
                  },
                  "plausibility": {
                    "do_test": True,
                    "minval": 0,
                    "maxval": 10000
                  }
                }
              }
            }
          }
        }

        settings = settings_var[self.var_name]
        sfx_lib = self.exp_file_paths.get_system_path("sfx_exp_lib")
        settings.update({"domain": {"domain_file": sfx_lib + "/domain.json"}})
        fg_file = self.exp_file_paths.get_system_file("archive_dir", "raw.nc", basedtg=self.dtg,
                                                      default_dir="default_archive_dir")
        settings.update({
            "firstguess": {
                "fg_file": fg_file,
                "fg_var": self.translation[self.var_name]
            }
        })

        print(self.obsdir)
        output = self.obsdir + "/qc_" + self.translation[self.var_name] + ".json"
        try:
            tests = self.config.get_setting("OBSERVATIONS#QC#" + self.var_name.upper() + "#TESTS")
        except Exception as e:
            tests = self.config.get_setting("OBSERVATIONS#QC#TESTS")

        indent = 2
        blacklist = {}
        debug = True
        print(surfex.__file__)
        tests = surfex.titan.define_quality_control(tests, settings, an_time, domain_geo=self.geo, debug=debug,
                                                    blacklist=blacklist)

        if "netatmo" in settings["sets"]:
            filepattern = self.config.get_setting("OBSERVATIONS#NETATMO_FILEPATTERN", check_parsing=False)
            settings["sets"]["netatmo"].update({"filepattern": filepattern})
            print(filepattern)
        if "bufr" in settings["sets"]:
            settings["sets"]["bufr"].update({"filepattern": self.obsdir + "/ob@YYYY@@MM@@DD@@HH@"})

        datasources = surfex.obs.get_datasources(an_time, settings["sets"])
        data_set = surfex.TitanDataSet(self.var_name, settings, tests, datasources, an_time, debug=debug)
        data_set.perform_tests()

        data_set.write_output(output, indent=indent)


class OptimalInterpolation(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        if self.var_name in self.translation:
            var = self.translation[self.var_name]
        else:
            raise Exception

        hlength = 30000
        vlength = 100000
        wlength = 0.5
        max_locations = 20
        elev_gradient = 0
        epsilon = 0.25

        hlength = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#HLENGTH", default=hlength)
        vlength = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#VLENGTH", default=vlength)
        wlength = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#WLENGTH", default=wlength)
        elev_gradient = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#GRADIENT",
                                                default=elev_gradient)
        max_locations = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#MAX_LOCATIONS",
                                                default=max_locations)
        epsilon = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#EPISLON", default=epsilon)
        minvalue = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#MINVALUE", default=None,
                                           abort=False)
        maxvalue = self.config.get_setting("OBSERVATIONS#OI#" + self.var_name.upper() + "#MAXVALUE", default=None,
                                           abort=False)
        input_file = self.archive + "/raw_" + var + ".nc"
        output_file = self.archive + "/an_" + var + ".nc"

        # Get input fields
        geo, validtime, background, glafs, gelevs = surfex.read_first_guess_netcdf_file(input_file, var)

        an_time = validtime
        # Read OK observations
        obs_file = self.exp_file_paths.get_system_file("obs_dir", "qc_" + var + ".json", basedtg=self.dtg,
                                                       default_dir="default_obs_dir")
        observations = surfex.dataset_from_file(an_time, obs_file, qc_flag=0)

        field = surfex.horizontal_oi(geo, background, observations, gelevs=gelevs,
                                     hlength=hlength, vlength=vlength, wlength=wlength,
                                     max_locations=max_locations, elev_gradient=elev_gradient,
                                     epsilon=epsilon, minvalue=minvalue, maxvalue=maxvalue)

        if os.path.exists(output_file):
            os.unlink(output_file)
        surfex.write_analysis_netcdf_file(output_file, field, var, validtime, gelevs, glafs, new_file=True, geo=geo)


class FirstGuess(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        firstguess = self.config.get_setting("SURFEX#IO#CSURFFILE") + self.suffix
        fg_file = self.exp_file_paths.get_system_file("first_guess_dir", firstguess, basedtg=self.fg_dtg,
                                                      validtime=self.dtg, default_dir="default_first_guess_dir")

        if os.path.islink(self.fg_guess_sfx):
            os.unlink(self.fg_guess_sfx)
        os.symlink(fg_file, self.fg_guess_sfx)


class CycleFirstGuess(FirstGuess):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        FirstGuess.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):

        firstguess = self.config.get_setting("SURFEX#IO#CSURFFILE") + self.suffix
        fg_file = self.exp_file_paths.get_system_file("first_guess_dir", firstguess, basedtg=self.fg_dtg,
                                                      validtime=self.dtg, default_dir="default_first_guess_dir")

        if os.path.islink(self.fc_start_sfx):
            os.unlink(self.fc_start_sfx)
        os.symlink(fg_file, self.fc_start_sfx)


class Oi2soda(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        yy = self.dtg.strftime("%y")
        mm = self.dtg.strftime("%m")
        dd = self.dtg.strftime("%d")
        hh = self.dtg.strftime("%H")
        obfile = "OBSERVATIONS_" + yy + mm + dd + "H" + hh + ".DAT"
        output = self.exp_file_paths.get_system_file("obs_dir", obfile, mbr=self.mbr, basedtg=self.dtg,
                                                     default_dir="default_obs_dir")

        t2m = None
        rh2m = None
        sd = None

        an_variables = {"t2m": False, "rh2m": False, "sd": False}
        obs_types = self.config.get_setting("SURFEX#ASSIM#OBS#COBS_M")
        nnco = self.config.get_setting("SURFEX#ASSIM#OBS#NNCO")
        snow_ass = self.config.get_setting("SURFEX#ASSIM#ISBA#UPDATE_SNOW_CYCLES")
        snow_ass_done = False
        if len(snow_ass) > 0:
            hh = int(self.dtg.strftime("%H"))
            for sn in snow_ass:
                if hh == int(sn):
                    snow_ass_done = True

        for ivar in range(0, len(obs_types)):
            if nnco[ivar] == 1:
                if obs_types[ivar] == "T2M":
                    an_variables.update({"t2m": True})
                elif obs_types[ivar] == "RH2M":
                    an_variables.update({"rh2m": True})
                elif obs_types[ivar] == "SWE":
                    if snow_ass_done:
                        an_variables.update({"sd": True})

        for var in an_variables:
            if an_variables[var]:
                var_name = self.translation[var]
                if var == "t2m":
                    t2m = {
                        "file": self.archive + "/an_" + var_name + ".nc",
                        "var": var_name
                    }
                elif var == "rh2m":
                    rh2m = {
                        "file": self.archive + "/an_" + var_name + ".nc",
                        "var": var_name
                    }
                elif var == "sd":
                    sd = {
                        "file": self.archive + "/an_" + var_name + ".nc",
                        "var": var_name
                    }

        surfex.oi2soda(self.dtg, t2m=t2m, rh2m=rh2m, sd=sd, output=output)
        # surfex.run_surfex_binary(binary)


class Qc2obsmon(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        kwargs.update({"dtg": self.dtg})
        outdir = self.extrarch + "/ecma_sfc/" + self.dtg.strftime("%Y%m%d%H") + "/"
        os.makedirs(outdir, exist_ok=True)
        output = outdir + "/ecma.db"
        kwargs.update({"output": output})

        if os.path.exists(output):
            os.unlink(output)
        nnco = self.config.get_setting("SURFEX#ASSIM#OBS#NNCO")
        obs_types = self.config.get_setting("SURFEX#ASSIM#OBS#COBS_M")
        for ivar in range(0, len(nnco)):
            if nnco[ivar] == 1:
                if len(obs_types) > ivar:
                    if obs_types[ivar] == "T2M":
                        var_in = "t2m"
                    elif obs_types[ivar] == "RH2M":
                        var_in = "rh2m"
                    elif obs_types[ivar] == "SWE":
                        var_in = "sd"
                    else:
                        raise NotImplementedError(obs_types[ivar])

                    if var_in != "sd":
                        var_name = self.translation[var_in]
                        kwargs.update({"qc": self.obsdir + "/qc_" + var_name + ".json"})
                        kwargs.update({"fg_file": self.archive + "/raw_" + var_name + ".nc"})
                        kwargs.update({"an_file": self.archive + "/an_" + var_name + ".nc"})
                        kwargs.update({"varname": var_in})
                        kwargs.update({"file_var": var_name})
                        surfex.write_obsmon_sqlite_file(**kwargs)


class FirstGuess4OI(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):

        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        validtime = self.dtg

        extra = ""
        symlink_files = {}
        if self.var_name in self.translation:
            var = self.translation[self.var_name]
            variables = [var]
            extra = "_" + var
            symlink_files.update({self.archive + "/raw.nc":  "raw" + extra + ".nc"})
        else:
            var_in = []
            nnco = self.config.get_setting("SURFEX#ASSIM#OBS#NNCO")

            for ivar in range(0, len(nnco)):
                if nnco[ivar] == 1:
                    if ivar == 0:
                        var_in.append("t2m")
                    elif ivar == 1:
                        var_in.append("rh2m")
                    elif ivar == 4:
                        var_in.append("sd")

            variables = []
            try:
                for var in var_in:
                    var_name = self.translation[var]
                    variables.append(var_name)
                    symlink_files.update({self.archive + "/raw_" + var_name + ".nc":  "raw.nc"})
            except ValueError:
                raise Exception("Variables could not be translated")

        variables = variables + ["altitude", "land_area_fraction"]

        output = self.archive + "/raw" + extra + ".nc"
        cache_time = 3600
        if "cache_time" in kwargs:
            cache_time = kwargs["cache_time"]
        cache = surfex.cache.Cache(True, cache_time)
        if os.path.exists(output):
            print("Output already exists " + output)
        else:
            self.write_file(output, variables, self.geo, validtime, cache=cache, sfx_exp_vars=self.sfx_exp_vars)

        # Create symlinks
        for target in symlink_files:
            linkfile = symlink_files[target]
            if os.path.lexists(target):
                os.unlink(target)
            os.symlink(linkfile, target)

    def write_file(self, output, variables, geo, validtime, cache=None, sfx_exp_vars=None):

        fg = None
        for var in variables:
            try:
                identifier = "INITIAL_CONDITIONS#FG4OI#" + var + "#"
                inputfile = self.config.get_setting(identifier + "INPUTFILE", basedtg=self.fg_dtg, validtime=self.dtg,
                                                    sfx_exp_vars=sfx_exp_vars)
            except Exception as e:
                identifier = "INITIAL_CONDITIONS#FG4OI#"
                inputfile = self.config.get_setting(identifier + "INPUTFILE", basedtg=self.fg_dtg, validtime=self.dtg,
                                                    sfx_exp_vars=sfx_exp_vars)
            try:
                identifier = "INITIAL_CONDITIONS#FG4OI#" + var + "#"
                fileformat = self.config.get_setting(identifier + "FILEFORMAT")
            except Exception as e:
                identifier = "INITIAL_CONDITIONS#FG4OI#"
                fileformat = self.config.get_setting(identifier + "FILEFORMAT")
            try:
                identifier = "INITIAL_CONDITIONS#FG4OI#" + var + "#"
                converter = self.config.get_setting(identifier + "CONVERTER")
            except Exception as e:
                identifier = "INITIAL_CONDITIONS#FG4OI#"
                converter = self.config.get_setting(identifier + "CONVERTER")

            print(inputfile, fileformat, converter)
            config_file = self.wd + "/config/first_guess.yml"
            config = yaml.load(open(config_file, "r"))
            defs = config[fileformat]
            defs.update({"filepattern": inputfile})

            converter_conf = config[var][fileformat]["converter"]
            if converter not in config[var][fileformat]["converter"]:
                raise Exception("No converter " + converter + " definition found in " + config_file + "!")

            print(converter)
            converter = surfex.read.Converter(converter, validtime, defs, converter_conf, fileformat, validtime)
            field = surfex.read.ConvertedInput(geo, var, converter).read_time_step(validtime, cache)
            field = np.reshape(field, [geo.nlons, geo.nlats])

            # Create file
            if fg is None:
                nx = geo.nlons
                ny = geo.nlats
                fg = surfex.create_netcdf_first_guess_template(variables, nx, ny, output)
                fg.variables["time"][:] = float(validtime.strftime("%s"))
                fg.variables["longitude"][:] = np.transpose(geo.lons)
                fg.variables["latitude"][:] = np.transpose(geo.lats)
                fg.variables["x"][:] = [i for i in range(0, nx)]
                fg.variables["y"][:] = [i for i in range(0, ny)]

            if var == "altitude":
                field[field < 0] = 0

            fg.variables[var][:] = np.transpose(field)

        if fg is not None:
            fg.close()


class LogProgress(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        stream = None
        if "stream" in kwargs:
            stream = kwargs["stream"]

        st = ""
        if stream is not None and stream != "":
            st = "_stream_" + stream
        progress_file = self.wd + "/progress" + st + ".json"

        # Update progress
        next_dtg = self.next_dtg.strftime("%Y%m%d%H")
        dtgbeg = self.dtgbeg.strftime("%Y%m%d%H")
        progress = {"DTG": next_dtg, "DTGBEG": dtgbeg}
        json.dump(progress, open(progress_file, "w"), indent=2)


class LogProgressPP(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)
        self.var_name = task.family1

    def execute(self, **kwargs):

        stream = None
        if "stream" in kwargs:
            stream = kwargs["stream"]

        st = ""
        if stream is not None and stream != "":
            st = "_stream_" + stream

        progress_pp_file = self.wd + "/progressPP" + st + ".json"

        # Update progress
        next_dtgpp = self.next_dtgpp.strftime("%Y%m%d%H")
        progress = {"DTGPP": next_dtgpp}
        json.dump(progress, open(progress_pp_file, "w"), indent=2)


class PrepareOiSoilInput(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        # Create FG
        raise NotImplementedError


class PrepareOiClimate(AbstractTask):
    def __init__(self, task,  config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        # Create CLIMATE.dat
        raise NotImplementedError


class PrepareSST(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        # Create CLIMATE.dat
        raise NotImplementedError


class PrepareLSM(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):

        file = self.archive + "/raw_nc"
        output = self.exp_file_paths.get_system_file("climdir", "LSM.DAT", check_existence=False,
                                                     default_dir="default_climdir")
        fileformat = "netcdf"
        converter = "none"
        kwargs = {
            "var": "land_area_fraction",
            "file":  file,
            "fileformat": fileformat,
            "output": output,
            "dtg": self.dtg,
            "geo": self.geo,
            "converter": converter,
        }
        print(kwargs)
        surfex.lsm_file_assim(**kwargs)


# Two test cases
class UnitTest(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        os.makedirs("/tmp/host0/job/test_start_and_run/", exist_ok=True)
        fh = open("/tmp/host1/scratch/sfx_home/test_start_and_run/unittest_ok", "w")
        fh.write("ok")
        fh.close()


class SleepingBeauty(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        print("Sleeping beauty...")
        print("Create /tmp/host1/scratch/sfx_home/test_start_and_run/SleepingBeauty")
        os.makedirs("/tmp/host0/job/test_start_and_run/", exist_ok=True)
        fh = open("/tmp/host1/scratch/sfx_home/test_start_and_run/SleepingBeauty", "w")
        fh.write("SleepingBeauty")
        fh.close()
        for i in range(0, 20):
            print("sleep.... ", i, "\n")
            time.sleep(1)


class SleepingBeauty2(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        print("Will the real Sleeping Beauty, please wake up! please wake up!")
        print("Create /tmp/host1/scratch/sfx_home/test_start_and_run/SleepingBeauty2")
        os.makedirs("/tmp/host0/job/test_start_and_run/", exist_ok=True)
        fh = open("/tmp/host1/scratch/sfx_home/test_start_and_run/SleepingBeauty2", "w")
        fh.write("SleepingBeauty")
        fh.close()


class WakeUpCall(AbstractTask):
    def __init__(self, task, config, system, exp_file_paths, progress, **kwargs):
        AbstractTask.__init__(self, task, config, system, exp_file_paths, progress, **kwargs)

    def execute(self, **kwargs):
        print("This job is default suspended and manually submitted!")
        print("Create /tmp/host1/scratch/sfx_home/test_start_and_run/test_submit")
        os.makedirs("/tmp/host0/job/test_start_and_run/", exist_ok=True)
        fh = open("/tmp/host1/scratch/sfx_home/test_start_and_run/test_submit", "w")
        fh.write("Job was submitted")
        fh.close()