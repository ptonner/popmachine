from app import app
from flask import Flask, render_template, request, jsonify, url_for, redirect, flash
from popmachine import Machine, models
from .forms import SearchForm, PlateCreate
from .plot import plotDataset
import pandas as pd
import re

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.charts import TimeSeries
from bokeh.resources import INLINE
from bokeh.util.string import encode_utf8
from bokeh.palettes import Spectral11, viridis

machine = Machine()

# def datasetHtml(ds,template,title='Dataset',color=None,*args, **kwargs):
#
#     ds = ds.copy()
#     ds.data.columns = ds.data.columns.astype(str)
#
#     ts = TimeSeries(ds.data)
#
#     numlines=len(ds.data.columns)
#
#     if color is None:
#         color = viridis(numlines)
#     else:
#         v = viridis(max(color)+1)
#         color = [v[c] for c in color]
#
#     fig = figure(title=title)
#     # fig.line(ds.data.index.values, ds.data, line_width=2)
#
#     fig.multi_line(xs=[ds.data.index.values]*ds.data.shape[1],
#     # fig.multi_line(xs=ds.data.index,
#                 ys = [ds.data[name].values for name in ds.data],
#                 # ys=ds.data,
#                 line_color=color,
#                 line_width=5)
#
#     js_resources = INLINE.render_js()
#     css_resources = INLINE.render_css()
#
#     # script, div = components(ts)
#     script, div = components(fig)
#
#     html = render_template(
#         template,
#         plot_script=script,
#         plot_div=div,
#         js_resources=js_resources,
#         css_resources=css_resources,
#         *args, **kwargs
#     )
#     return encode_utf8(html)

@app.route('/')
def index():
    plates = machine.plates()
    searchform = SearchForm()

    return render_template("index.html", plates=plates, searchform=searchform)

@app.route('/plates/')
def plates():
    plates = machine.plates()
    searchform = SearchForm()

    return render_template("plates.html", plates=plates, searchform=searchform)

@app.route('/plate/<platename>')
def plate(platename):
    searchform = SearchForm()
    plate = machine.session.query(models.Plate).filter(models.Plate.name==platename).one_or_none()

    experimentalDesigns = machine.session.query(models.ExperimentalDesign)\
                .join(models.well_experimental_design)\
                .join(models.Well)\
                .filter(models.Well.id.in_([w.id for w in plate.wells]))

    designs = machine.session.query(models.Design)\
                .join(models.ExperimentalDesign)\
                .join(models.well_experimental_design)\
                .join(models.Well)\
                .filter(models.Well.id.in_([w.id for w in plate.wells]))


    return render_template("plate.html", plate=plate, experimentalDesigns=experimentalDesigns, designs=designs, searchform = searchform)

@app.route('/plate-delete/<platename>', methods=['GET', 'POST'])
def plate_delete(platename):
    searchform = SearchForm()

    if request.method=='GET':
        return render_template('plate-delete.html', searchform = searchform, platename=platename)
    else:
        plate = machine.session.query(models.Plate).filter(models.Plate.name==platename).one_or_none()
        machine.deletePlate(plate)

        return redirect(url_for('plates'))

@app.route('/plate-create/', methods=['GET', "POST"])
def plate_create():

    searchform = SearchForm()

    if request.method=="GET":
        form = PlateCreate()
        return render_template("plate-create.html", form=form, searchform = searchform)
    else:

        name = request.form['name']
        ignore = request.form['ignore'].split(",")
        f = request.files['data']
        data = pd.read_csv(f)

        if 'design' in request.files:
            f = request.files['design']
            meta = pd.read_csv(f)

            if len(ignore) > 0:
                for i in ignore:
                    if i == "":
                        continue
                    del meta[i]
        else:
            meta = None

        if request.form['source'] == 'csv':
            machine.createPlate(name, data, meta)
        else:
            pass

        return redirect(url_for('plates'))


@app.route('/designs/')
def designs():
    designs = machine.designs()
    searchform = SearchForm()

    return render_template("designs.html", designs=designs, searchform=searchform)

@app.route('/design/<_id>')
@app.route('/design/<_id>/<plate>')
def design(_id, plate=None):
    searchform = SearchForm()

    design = machine.session.query(models.Design)\
                .filter(models.Design.id==_id).one_or_none()

    values = machine.session.query(models.ExperimentalDesign)\
                .join(models.Design)\
                .filter(models.Design.id==_id)

    wells = machine.session.query(models.Well)\
                .join(models.well_experimental_design)\
                .join(models.ExperimentalDesign)\
                .join(models.Design)\
                .filter(models.Design.id==_id)

    if not plate is None:
        wells = wells.join(models.Plate).filter(models.Plate.name==plate)

        values = values.join(models.well_experimental_design)\
                    .join(models.Well)\
                    .join(models.Plate).filter(models.Plate.name==plate)

    ds = machine.get(wells, include=[design.name])

    assert not any(ds.meta[design.name].isnull())

    # else:
    #     plate = ""

    color = map(lambda x: ds.meta[design.name].unique().tolist().index(x), ds.meta[design.name])

    return plotDataset(ds, 'design.html', color=ds.meta[design.name], values=values, design=design, searchform=searchform, plate=plate)
    # return render_template("design.html", wells=wells, design=design, searchform=searchform)

@app.route('/experimentaldesign/<_id>')
@app.route('/experimentaldesign/<_id>/<plate>')
def experimentalDesign(_id, plate=None):
    searchform = SearchForm()

    ed = machine.session.query(models.ExperimentalDesign)\
                .filter(models.ExperimentalDesign.id==_id).one_or_none()

    wells = machine.session.query(models.Well)\
                .join(models.well_experimental_design)\
                .join(models.ExperimentalDesign)\
                .filter(models.ExperimentalDesign.id==_id)

    if not plate is None:
        wells = wells.join(models.Plate).filter(models.Plate.name==plate)

    return render_template("experimental-design.html", wells=wells, experimentalDesign=ed, searchform=searchform)

@app.route('/search/',methods=['GET', 'POST'])
def search():

    searchform = SearchForm()

    if request.method=='GET':
        return render_template("search.html", searchform=searchform)
    else:
        groups = re.findall("(([0-9a-zA-Z -]+)=([0-9a-zA-Z ,.-]+))", request.form['search'])

        kwargs = {}
        for _, k, v in groups:
            k = k.strip().rstrip()
            v = v.split(",")
            v = [z.strip().rstrip() for z in v]
            kwargs[k] = v

        # wells = machine.filter(**kwargs)

        ds = machine.search(**kwargs)

        if ds is None:
            flash('No data found for search: %s'%str(kwargs))
            return render_template("dataset.html", searchform=searchform)
        else:
            color = None
            # if len(groups)>0:
            for k, v in kwargs.iteritems():
                if str(k) in ['include', 'plates']:
                    continue
                color = map(lambda x: ds.meta[k].unique().tolist().index(x), ds.meta[k])
                break

            return plotDataset(ds, 'dataset.html', searchform=searchform, dataset=ds)
