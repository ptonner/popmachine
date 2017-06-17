
# from . import machine
from popmachine import models
from .forms import SearchForm, DesignForm, PhenotypeForm
from .plot import plotDataset
from ..phenotype import design_space
from safeurl import is_safe_url
# from security import ts

import re
import flask
import pandas as pd
from flask import current_app, render_template, request, jsonify, url_for, redirect, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from sqlalchemy import or_, not_
from wtforms import SelectField, StringField, TextAreaField

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.charts import TimeSeries
from bokeh.resources import INLINE
from bokeh.util.string import encode_utf8
from bokeh.palettes import Spectral11, viridis

# machine = Machine()
# login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return machine.session.query(models.User).filter_by(id=user_id).one_or_none()


@current_app.route('/')
def index():

    if not current_user.is_authenticated:
        projects = machine.session.query(
            models.Project).filter_by(published=True).all()
        plates = machine.session.query(models.Plate).join(
            models.Project).filter(models.Project.published).all()
        designs = machine.session.query(models.Design).join(
            models.Project).filter(models.Project.published).all()

        phenotypes = machine.session.query(models.Phenotype).join(
            models.Project).filter(models.Project.published).all()

    else:
        projects = machine.session.query(models.Project).filter(
            or_(models.Project.owner == current_user, models.Project.published)).all()
        plates = machine.session.query(models.Plate).join(
            models.Project).filter(models.Project.owner == current_user).all()
        designs = machine.session.query(models.Design).join(models.Project).filter(
            or_(models.Project.owner == current_user, models.Project.published)).all()

        phenotypes = machine.session.query(models.Phenotype).join(models.Project).filter(
            or_(models.Project.owner == current_user, models.Project.published)).all()

    if len(projects) > 5:
        projects = projects[:5]
    if len(plates) > 5:
        plates = plates[:5]
    if len(designs) > 5:
        designs = designs[:5]
    if len(phenotypes) > 5:
        phenotypes = phenotypes[:5]

    searchform = SearchForm()

    return render_template("index.html", projects=projects, plates=plates, designs=designs, phenotypes=phenotypes, searchform=searchform)


@current_app.route('/bgreat')
def bgreat():
    searchform = SearchForm()
    return render_template("bgreat.html", searchform=searchform)


@current_app.route('/designs/')
def designs():
    if current_user.is_authenticated:
        designs = machine.session.query(models.Design).join(models.Project).filter(
            or_(models.Project.published, models.Project.owner == current_user)).all()
    else:
        designs = machine.session.query(models.Design).join(
            models.Project).filter(models.Project.published).all()
    searchform = SearchForm()

    return render_template("designs.html", designs=designs, searchform=searchform)


@current_app.route('/design/<_id>', methods=['GET'])
@current_app.route('/design/<_id>/<plate>')
def design(_id, plate=None):
    searchform = SearchForm()
    designform = DesignForm()

    design = machine.session.query(models.Design)\
        .filter(models.Design.id == _id).one_or_none()

    designform.type.default = design.type
    designform.process()

    if request.method == 'GET':

        designform.type.default = design.type

        values = machine.session.query(models.ExperimentalDesign)\
            .join(models.Design)\
            .filter(models.Design.id == _id)

        wells = machine.session.query(models.Well)\
            .join(models.well_experimental_design)\
            .join(models.ExperimentalDesign)\
            .join(models.Design)\
            .filter(models.Design.id == _id)

        if not plate is None:
            wells = wells.join(models.Plate).filter(models.Plate.name == plate)

            values = values.join(models.well_experimental_design)\
                .join(models.Well)\
                .join(models.Plate).filter(models.Plate.name == plate)

        ds = machine.get(wells, include=[design.name])

        assert not any(ds.meta[design.name].isnull())

        color = map(lambda x: ds.meta[design.name].unique(
        ).tolist().index(x), ds.meta[design.name])

        return plotDataset(ds, 'design.html', color=ds.meta[design.name], values=values, design=design,
                           searchform=searchform, plate=plate, designform=designform)

    else:
        design.type = request.form['type']
        machine.session.commit()

        return redirect(url_for('design.design', _id=design.id))


@current_app.route('/design_edit/<_id>', methods=['GET', 'POST'])
@login_required
def design_edit(_id):

    searchform = SearchForm()

    design = machine.session.query(models.Design)\
        .filter(models.Design.id == _id).one_or_none()

    class DynamicDesignForm(DesignForm):

        description = TextAreaField('description', default=design.description)
        protocol = TextAreaField('protocol', default=design.protocol)

    designform = DynamicDesignForm()

    designform.type.default = design.type
    designform.description.default = design.description
    designform.protocol.default = design.protocol
    designform.process()

    if request.method == 'GET':

        return render_template('design-edit.html', searchform=searchform, designform=designform, design=design)

    else:
        design.type = request.form['type']
        design.description = request.form['description']
        design.protocol = request.form['protocol']
        machine.session.commit()

        return redirect(url_for('design.design', _id=design.id))


@current_app.route('/experimentaldesign/<_id>')
@current_app.route('/experimentaldesign/<_id>/<plate>')
def experimentalDesign(_id, plate=None):
    searchform = SearchForm()

    ed = machine.session.query(models.ExperimentalDesign)\
                .filter(models.ExperimentalDesign.id == _id).one_or_none()

    wells = machine.session.query(models.Well)\
        .join(models.well_experimental_design)\
        .join(models.ExperimentalDesign)\
        .filter(models.ExperimentalDesign.id == _id)

    if not plate is None:
        wells = wells.join(models.Plate).filter(models.Plate.name == plate)

    ds = machine.get(wells, include=[ed.design.name])
    ds.floor()

    return plotDataset(ds, "experimental-design.html", color=ds.meta[ed.design.name], wells=wells, experimentalDesign=ed, searchform=searchform)
    return render_template("experimental-design.html", wells=wells, experimentalDesign=ed, searchform=searchform)


@current_app.route('/search/', methods=['GET', 'POST'])
def search():

    searchform = SearchForm()

    if request.method == 'GET':
        return render_template("search.html", searchform=searchform)
    else:
        groups = re.findall(
            "(([0-9a-zA-Z -._()]+)=([0-9a-zA-Z ,.-_()]+))", request.form['search'])

        kwargs = {}
        for _, k, v in groups:
            k = k.strip().rstrip()
            v = v.split(",")
            v = [z.strip().rstrip() for z in v]
            kwargs[k] = v

        session['designs'] = [d.id for d in machine.session.query(
            models.Design).filter(models.Design.name.in_(kwargs.keys()))]
        session['wells'] = [w.id for w in machine.filter(**kwargs)]
        ds = machine.search(**kwargs)

        # print ds.data.head()

        if ds is None:
            flash('No data found for search: %s' % str(kwargs))
            return render_template("dataset.html", searchform=searchform)
        else:
            # color = None
            # # if len(groups)>0:
            # for k, v in kwargs.iteritems():
            #     if str(k) in ['include', 'plates']:
            #         continue
            #     color = map(lambda x: ds.meta[k].unique().tolist().index(x), ds.meta[k])
            #     break

            # return plotDataset(ds, 'dataset.html', searchform=searchform,
            # dataset=ds)
            return plotDataset(ds, 'dataset.html', searchform=searchform)


@current_app.route('/phenotype/<id>')
def phenotype(id):
    searchform = SearchForm()

    phenotype = machine.session.query(models.Phenotype).filter_by(id=id)
    if not current_user.is_authenticated:
        phenotype = phenotype.join(models.Project).filter(
            models.Project.published)
    else:
        phenotype = phenotype.join(models.Project).filter(
            or_(models.Project.owner == current_user, models.Project.published))
    phenotype = phenotype.one_or_none()

    if not phenotype:
        flask.flash('no phenotype found or incorrect permissions!')
        return flask.redirect(url_for('misc.phenotypes'))

    wells = machine.session.query(models.Well).filter(
        models.Well.id.in_([w.id for w in phenotype.wells]))
    ds = machine.get(wells, include=[d.name for d in phenotype.designs])

    dsp = design_space.design_space(machine.session, phenotype)

    values = {}
    for d in phenotype.designs:
        q = machine.session.query(models.ExperimentalDesign)\
                   .join(models.well_experimental_design)\
                   .join(models.Well)\
                   .filter(models.ExperimentalDesign.design == d)\
                   .filter(models.Well.id.in_([w.id for w in wells]))

        values[d.name] = q.all()

    return plotDataset(ds, 'phenotype.html', searchform=searchform, phenotype=phenotype, values=values, dsp=dsp, dataSet=ds)


@current_app.route('/phenotypes')
def phenotypes():
    searchform = SearchForm()
    if not current_user.is_authenticated:
        phenotypes = machine.session.query(models.Phenotype).join(
            models.Project).filter(models.Project.published).all()

    else:
        phenotypes = machine.session.query(models.Phenotype).join(models.Project).filter(
            or_(models.Project.owner == current_user, models.Project.published)).all()

    return render_template('phenotypes.html', phenotypes=phenotypes, searchform=searchform)


@current_app.route('/phenotype-create', methods=['GET', 'POST'])
@login_required
def phenotype_create():
    searchform = SearchForm()
    phenotype_form = PhenotypeForm()

    if request.method == 'GET':
        return render_template("phenotype-edit.html", searchform=searchform, form=phenotype_form, operation='create')
    else:
        wells = machine.session.query(models.Well).filter(
            models.Well.id.in_(session.pop('wells', None))).all()
        designs = machine.session.query(models.Design).filter(
            models.Design.id.in_(session.pop('designs', None))).all()
        name = request.form['name']

        project = wells[0].plate.project

        phenotype = models.Phenotype(
            name=name, owner=current_user, wells=wells, designs=designs, project=project)
        phenotype.download_phenotype()

        machine.session.add(phenotype)
        machine.session.commit()

        return redirect(url_for('phenotype', id=phenotype.id))


@login_manager.unauthorized_handler
def unauthorized():
    # do stuff
    flask.flash('you must be logged in to do that!')
    return redirect(flask.url_for('misc.login'))
