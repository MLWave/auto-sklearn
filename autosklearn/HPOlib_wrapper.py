'''
Created on Dec 17, 2014

@author: Aaron Klein
'''

import functools
import lockfile
import os
import time

try:
    import cPickle as pickle
except:
    import pickle

from HPOlibConfigSpace import configuration_space

try:
    from HPOlib.benchmark_util import parse_cli
except:
    from HPOlib.benchmarks.benchmark_util import parse_cli

from autosklearn.data.data_manager import DataManager
from autosklearn.models.holdout_evaluator import HoldoutEvaluator
from autosklearn.models.cv_evaluator import CVEvaluator
from autosklearn.models.test_evaluator import TestEvaluator
from autosklearn.models.paramsklearn import get_configuration_space


def store_and_or_load_data(outputdir, dataset, data_dir):
    save_path = os.path.join(outputdir, dataset + "_Manager.pkl")
    if not os.path.exists(save_path):
        lock = lockfile.LockFile(save_path)
        while not lock.i_am_locking():
            try:
                lock.acquire(timeout=60)    # wait up to 60 seconds
            except lockfile.LockTimeout:
                lock.break_lock()
                lock.acquire()
        print "I locked", lock.path
        # It is not yet sure, whether the file already exists
        try:
            if not os.path.exists(save_path):
                D = DataManager(dataset, data_dir, verbose=True,
                                encode_labels=True)
                fh = open(save_path, 'w')
                pickle.dump(D, fh, -1)
                fh.close()
            else:
                D = pickle.load(open(save_path, 'r'))
        except:
            raise
        finally:
            lock.release()
    else:
        D = pickle.load(open(save_path, 'r'))
    return D


def get_new_run_num():
    counter_file = os.path.join(os.getcwd(), "num_run")
    lock = lockfile.LockFile(counter_file)
    with lock:
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as fh:
                fh.write("0")
            num = 0
        else:
            with open(counter_file, "r") as fh:
                num = int(fh.read())
            num += 1
            with open(counter_file, "w") as fh:
                fh.write(str(num).zfill(4))

    return num


def main(args, params):
    """This wrapper has three different operation modes:

    * CV: useful for the Tweakathon
    * 1/3 test split: useful to evaluate a configuration
    * cv on 2/3 train split: useful to optimize hyperparameters in a training
      mode before testing a configuration on the 1/3 test split.

    It must by no means be used for the Auto part of the competition!
    """

    for key in params:
        try:
            params[key] = float(params[key])
        except:
            pass

    basename = args['dataset']
    input_dir = args['data_dir']
    test = args.get('test')
    cv = args.get('cv')
    if cv is not None:
        cv = int(float(cv))

    seed = args.get('seed')
    if seed is not None:
        seed = int(float(seed))
    else:
        seed = 1

    fold = int(float(args['fold']))
    folds = int(float(args['folds']))

    output_dir = os.getcwd()

    D = store_and_or_load_data(data_dir=input_dir, dataset=basename,
                               outputdir=output_dir)

    cs = get_configuration_space(D.info)
    configuration = configuration_space.Configuration(cs, **params)
    metric = D.info['metric']

    # Train/test split
    if cv is None and test is None and folds == 1:
        evaluator = HoldoutEvaluator(D, configuration,
                                     with_predictions=True,
                                     all_scoring_functions=True,
                                     output_y_test=True,
                                     seed=seed)
        evaluator.fit()
        evaluator.finish_up()

    elif cv is None and test is not None and folds == 1:
        evaluator = TestEvaluator(D, configuration,
                                  all_scoring_functions=True,
                                  seed=seed)
        evaluator.fit()
        scores = evaluator.predict()
        duration = time.time() - evaluator.starttime

        score = scores[metric]
        additional_run_info = ";".join(["%s: %s" % (m_, value)
                                        for m_, value in scores.items()])
        additional_run_info += ";" + "duration: " + str(duration)

        print "Result for ParamILS: %s, %f, 1, %f, %d, %s" % (
            "SAT", abs(duration), score, evaluator.seed, additional_run_info)

    # CV on the whole dataset
    elif cv is not None and test is None and folds == 1:
        if test is not None:
            raise ValueError("Test mode not supported with CV.")
        evaluator = CVEvaluator(D, configuration, with_predictions=True,
                                all_scoring_functions=True, output_y_test=True,
                                cv_folds=cv, seed=seed)
        evaluator.fit()
        evaluator.finish_up()

    elif folds != 1 and cv is not None and folds == cv:
        if test is not None:
            raise ValueError("Test mode not supported with CV.")
        evaluator = CVEvaluator(D, configuration, all_scoring_functions=True,
                                cv_folds=cv, seed=seed)
        evaluator.partial_fit(fold)
        scores = evaluator.predict()
        duration = time.time() - evaluator.starttime

        score = scores[metric]
        additional_run_info = ";".join(["%s: %s" % (m_, value)
                                        for m_, value in scores.items()])
        additional_run_info += ";" + "duration: " + str(duration)

        print "Result for ParamILS: %s, %f, 1, %f, %d, %s" % (
            "SAT", abs(duration), score, evaluator.seed, additional_run_info)

    else:
        raise ValueError("Must choose a legal mode.")


if __name__ == "__main__":
    starttime = time.time()
    args, params = parse_cli()
    main(args, params)