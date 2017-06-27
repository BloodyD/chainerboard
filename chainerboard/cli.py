#! /usr/bin/env python

import json
import os
import re

import click
import colorlover as cl
import numpy as np
import plotly
from flask import Flask, render_template, redirect, url_for, Response

import chainerboard

script_dir = os.path.dirname(__file__)


app = Flask(
    __name__,
    template_folder=os.path.join('..', 'templates'),
    static_folder=os.path.join('..', 'static')
)
app.debug = True

logdir = None


def load_data():
    global logdir
    reporter = chainerboard.Reporter.load(logdir)
    print 'loaded json'
    return reporter.to_timeline()


def moving_average(x, y, window):
    weights = np.repeat(1.0, window) / window
    ma = np.convolve(y, weights, 'valid')
    x = x[window // 2:len(y) - (window // 2)]
    return x, ma


@app.route('/')
def index():
    return redirect(url_for('events'))


@app.route('/events.html')
def events():
    return render_template('layouts/events.html')


def combine_jsons(**kwargs):
    """
    Combine pre-encoded json object (str) to a single json string. This is
    essentially the same as
    ``json.dumps({k: json.loads(v) for k, j in kwargs.iteritems})`` but without
    loading of the json string.

    Args:
        **kwargs (str): Each parameter should be something that was encoded
            with json.dumps. You should pass ``json.dumps(s)`` if you want to
            use str object.

    Returns:
        str: Combined json.

    """
    ret = json.dumps({k : '==%s==' % k for k in kwargs.keys()})
    search_str = {'"==%s=="' % k: v for k, v in kwargs.iteritems()}
    pattern = re.compile(r'(' + '|'.join(search_str.keys()) + r')')
    return pattern.sub(lambda x: search_str[x.group()], ret)


@app.route('/events/data')
def add_numbers():
    graphs = []
    timeline = load_data()
    colorpalette = cl.to_numeric(cl.scales['7']['qual']['Set1'])

    for g, group in timeline.iteritems():
        data = []
        for (l, d), color in zip(group.iteritems(), colorpalette):
            color = '#{:02X}{:02X}{:02X}'.format(*map(int, color))
            data.append(dict(
                x=d[0],
                y=d[1],
                type='scatter',
                marker={'color': color},
                name=l,
                opacity=0.3,
            ))
            if len(d[0]) > 11:
                x, y = moving_average(d[0], d[1], 11)
                data.append(dict(
                    x=x,
                    y=y,
                    type='scatter',
                    name=l + '(window=11)',
                    marker={'color': color},
                    opacity=0.9
                ))

        graphs.append(
            dict(data=data,
                 layout=dict(
                     title=g,
                     xaxis={'title': 'steps'},
                     yaxis={'type': 'log'}
                 )
                 ))

    ids = ['graph-{}'.format(i) for i, _ in enumerate(graphs)]

    graphs_json = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)

    ret = combine_jsons(
        ids=json.dumps(ids),
        graphs=graphs_json
    )

    print 'created graph json'
    # do not use jsonify because we want to use custom encoder
    return Response(ret, mimetype='application/json')


@click.command()
@click.argument('inputfile', type=click.Path(exists=True))
@click.option('-p', '--port', type=int, default=6006)
def cli(inputfile, port):
    global logdir
    logdir = inputfile
    app.run(host='0.0.0.0', port=port)
