"""
Idea:
implement magic that takes the path to the experiment configuration


plotting function:
- iteration plots
    * learner, config, repetition, iteration
- results plots
    * config, results

"""
import os
from typing import Callable, List, Union

import matplotlib.pyplot as plt
from IPython.core.getipython import get_ipython
from IPython.core.magic import register_line_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
from IPython.display import display
from ipywidgets import Box, FloatProgress, HBox, Label, Layout, Output, Tab, Widget
from matplotlib.figure import Figure
from pandas import DataFrame

from cluster_work import ClusterWork

__iteration_plot_functions = {}
__results_plot_functions = {}

__experiment_class: ClusterWork = None
__experiment_config = None
__experiment_selectors = None


def register_iteration_plot_function(name: str):
    def register_iteration_plot_function_decorator(plot_function: Callable[[ClusterWork, int, int, List],
                                                                           Union[Figure, Widget]]):
        global __iteration_plot_functions
        __iteration_plot_functions[name] = plot_function
        return plot_function
    return register_iteration_plot_function_decorator


def register_results_plot_function(name: str):
    def register_results_plot_function_decorator(plot_function: Callable[[str, DataFrame, plt.Axes], None]):
        global __results_plot_functions
        __results_plot_functions[name] = plot_function
        return plot_function
    return register_results_plot_function_decorator


@register_line_magic
def set_experiment_class(line: str):
    global __experiment_class
    __experiment_class = get_ipython().ev(line)


@register_line_magic
@magic_arguments()
@argument('config', type=str)
@argument('-e', '--experiments', nargs='*')
@argument('-f', '--filter', nargs='*', help='filter strings that are applied on the experiment names')
def load_experiment(line: str):
    # TODO add tab completion for file
    # read line, split at white spaces load experiments with selectors
    args = parse_argstring(load_experiment, line)
    # experiment_config = splits.pop(0)
    # experiment_selectors = splits

    # check if experiment config exists and load experiments
    if not os.path.exists(args.config):
        raise Warning('path does not exist: {}'.format(args.config))
    else:
        global __experiments, __experiment_config, __experiment_selectors
        __experiment_config = args.config
        __experiment_selectors = args.experiments

        with open(__experiment_config, 'r') as f:
            __experiments = __experiment_class.load_experiments(f, __experiment_selectors)

        if args.filter is not None:
            __experiments = list(filter(lambda c: all([_f in c['name'] for _f in args.filter]), __experiments))
        else:
            __experiments = __experiments

        get_ipython().user_ns['experiments'] = __experiments


@register_line_magic
@magic_arguments()
@argument('-r', '--repetition', type=int, help='the repetition', default=0)
@argument('-i', '--iteration', type=int, help='the iteration to plot', default=0)
def restore_experiment_state(line: str):
    args = parse_argstring(restore_experiment_state, line)
    global __instances, __instantiated_experiments
    __instances = list()
    __instantiated_experiments = list()

    with Output():
        for exp in get_ipython().user_ns['experiments']:
            exp_instance = __experiment_class.init_from_config(exp, args.repetition, args.iteration)
            if exp_instance:
                __instances.append(exp_instance)
                __instantiated_experiments.append(exp)

    get_ipython().user_ns['experiment_instances'] = __instances


@register_line_magic
@magic_arguments()
@argument('plotter_name', type=str, help='the name of the plotter function')
@argument('args', nargs='*', help='extra arguments passed to the filter function')
def plot_iteration(line: str):
    """call a registered plotter function for the given repetition and iteration"""
    args = parse_argstring(plot_iteration, line)

    items = []

    from ipywidgets.widgets.interaction import show_inline_matplotlib_plots

    global __instances, __instantiated_experiments
    for exp in __instances:
        out = Output()
        items.append(out)
        with out:
            # clear_output(wait=True)
            __iteration_plot_functions[args.plotter_name](exp, args.args)
            show_inline_matplotlib_plots()

    if len(items) > 1:
        tabs = Tab(children=items)
        for i, exp in enumerate(__instantiated_experiments):
            tabs.set_title(i, '...' + exp['name'][-15:])
        display((tabs,))
    elif len(items) == 1:
        return items[0]
    else:
        import warnings
        warnings.warn('No plots available for {} with args {}'.format(args.plotter_name, args.args))


def __plot_iteration_completer(_ipython, _event):
    return __iteration_plot_functions.keys()


@register_line_magic
@magic_arguments()
@argument('plotter_name', type=str, help='the name of the plotter function')
@argument('column', type=str, help='column of the results DataFrame to plot')
@argument('-i', '--individual', action='store_true', help='plot each experiment in a single axes object')
def plot_results(line: str):
    args = parse_argstring(plot_results, line)

    # global __experiments, __results_plot_functions
    config_results = [(config, ClusterWork.load_experiment_results(config)) for config in __experiments]
    config_results = list(map(lambda t: (t[0], t[1][args.column]), filter(lambda t: t[1] is not None, config_results)))

    f = plt.figure()
    if args.individual:
        axes = f.subplots(len(config_results), 1)
    else:
        axes = [f.subplots(1, 1)] * len(config_results)

    for config_result, ax in zip(config_results, axes):
        config, result = config_result
        ax.set_xlim(0, config['iterations'])
        __results_plot_functions[args.plotter_name](config['name'], result, ax)


def __create_exp_progress_box(name, exp_progress, rep_progress, show_full_progress=False):
    exp_progress_layout = Layout(display='flex', flex_flow='column', align_items='stretch', width='100%')
    exp_progress_bar = HBox([FloatProgress(value=exp_progress, min=.0, max=1., bar_style='info'), Label(name)])

    if show_full_progress:
        rep_progress_layout = Layout(display='flex', flex_flow='column', align_items='stretch',
                                     align_self='flex-end', width='80%')

        items = [FloatProgress(value=p, min=.0, max=1., description=str(i)) for i, p in enumerate(rep_progress)]
        rep_progress_box = Box(children=items, layout=rep_progress_layout)

        return Box(children=[exp_progress_bar, rep_progress_box], layout=exp_progress_layout)
    else:
        return exp_progress_bar


@register_line_magic
def show_progress(line: str):
    show_full_progress = line == 'full'

    global __experiment_config, __experiment_selectors

    with open(__experiment_config, 'r') as f:
        total_progress, experiments_progress = ClusterWork.get_progress(f, __experiment_selectors)

    box_layout = Layout(display='flex', flex_flow='column', align_items='stretch', widht='100%')
    items = [__create_exp_progress_box(*progress, show_full_progress) for progress in experiments_progress]

    total_progress_bar = FloatProgress(value=total_progress, min=.0, max=1., description='Total', bar_style='success')

    return Box(children=items + [total_progress_bar], layout=box_layout)


def load_ipython_extension(ipython):
    global __iteration_plot_functions, __results_plot_functions
    # ipython.push(['__experiment_config', '__experiment_selectors'])

    ipython.set_hook('complete_command', __plot_iteration_completer, re_key='%plot_iteration')
    # ipython.set_hook('complete_command', lambda e: __results_plot_functions.keys(), re_key='%plot_results')


del register_line_magic
