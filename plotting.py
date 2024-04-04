#!/usr/bin/env python3
import os
import simulator
from importlib import reload
import sys
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import cm


TEST_DIRECTORY = './tests'


def plot_data(algo_num, data_dict):
    fig = plt.figure(figsize=(8,8))
    algo = {'1':'BBA-2', '2':'Robust_MPC'}
    for i, (metric_name, data) in enumerate(data_dict.items()):
        tick_labels = ['low', 'med', 'high']
        x_ticks = np.arange(data.shape[1])
        y_ticks = np.arange(data.shape[0])
        x, y = np.meshgrid(x_ticks, y_ticks)
        z = data

        ax = fig.add_subplot(int(f'22{i+1}'), projection='3d')
        # x = x.ravel()
        # y = y.ravel()
        # z = data.ravel()
        # ax.bar3d( x, y, np.zeros_like(z), 1, 1, z , alpha=0.75)
        ax.plot_wireframe( x, y, z)
        ax.set_title(metric_name)
        ax.set_xlabel('variance')
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(tick_labels)
        ax.set_ylabel('average')
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(tick_labels)

    plt.suptitle(algo[algo_num])
    plt.tight_layout()
    plt.savefig(algo[algo_num])

def main(student_algo: str):
    """
    Runs simulator and student algorithm on all tests in TEST_DIRECTORY
    Args:
        student_algo : Student algorithm to run
    """
    # Run main loop, print output
    shape = (3,3)
    qualities  = np.zeros(shape)
    variations = np.zeros(shape)
    rebuffs    = np.zeros(shape)
    qoes       = np.zeros(shape)

    sum_qoe = 0
    print(f'\nTesting student algorithm {student_algo}')
    for test in os.listdir(TEST_DIRECTORY):
        reload(simulator)
        quality, variation, rebuff, qoe = simulator.main(os.path.join(TEST_DIRECTORY, test), student_algo, False, False)
        print(f'\tTest {test: <12}:'
              f' Total Quality {quality:8.2f},'
              f' Total Variation {variation:8.2f},'
              f' Rebuffer Time {rebuff:8.2f},'
              f' Total QoE {qoe:8.2f}')
        sum_qoe += qoe

        if   'hi_avg' in test: avg = 2
        elif 'mi_avg' in test: avg = 1
        elif 'lo_avg' in test: avg = 0

        if   'hi_var' in test: var = 2
        elif 'mi_var' in test: var = 1
        elif 'lo_var' in test: var = 0 

        qualities[avg][var]  = quality
        variations[avg][var] = variation
        rebuffs[avg][var]    = rebuff
        qoes[avg][var]       = qoe

    print(f'\n\tAverage QoE over all tests: {sum_qoe / len(os.listdir(TEST_DIRECTORY)):.2f}')

    data = {'QOE':qoes, 'Rebuffer Time (s)':rebuffs, 'Variation (# of changes)':variations, 'Quality Points':qualities}
    plot_data(student_algo, data)


if __name__ == "__main__":
    for algo in os.listdir('./student'):
        if algo[:len('student')] != 'student':
            continue
        name = algo[len('student'):].split('.')[0]
        main(name)
