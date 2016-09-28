import os
import re
import json
import random
import urllib
import datetime
from flask import render_template, redirect, url_for, abort, flash, request,current_app, make_response
from flask_login import login_user, logout_user,login_required, current_user
from .. import db
from ..models import Permission, Role, User, Post
from ..email import send_email
from . import main
from .forms import PostForm,EditForm,LoginForm,ChangePasswordForm

def gen_rnd_filename():
    filename_prefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return '%s%s' % (filename_prefix, str(random.randrange(1000, 10000)))


@main.route('/', methods=['GET', 'POST'])
def index():
    post_form = PostForm()
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],error_out=False)
    posts = pagination.items
    return render_template('index.html', post_form=post_form, posts=posts, pagination=pagination)


@main.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    post_form = PostForm()
    if  current_user.can(Permission.WRITE_ARTICLES) and post_form.data['submit']: #request.method == 'POST':  #request("save")=="保存"
        post_form.title.data = request.form.get('title')
        post_form.body_html.data = request.form.get('content')
        post = Post(title=post_form.title.data, body_html=post_form.body_html.data,author=current_user._get_current_object())
        db.session.add(post)
        newpost = Post.query.order_by(Post.id.desc()).first_or_404()
        return render_template('blog.html', post=newpost)
    return render_template('create.html', post_form=post_form)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    edit_form = EditForm()
    if edit_form.data['submit']:
        post.title = request.form.get('title')
        post.body_html = request.form.get('content')
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.index', id=post.id))
    if edit_form.data['delete']:
        db.session.delete(post)
        flash('The post has been delete.')
        return redirect(url_for('.index'))
        #return render_template('edit_post.html', form=form,delete_form=delete_form)

    if edit_form.data['cancel']:
        return redirect(url_for('.index'))

    edit_form.title.data = post.title
    edit_form.body_html.data = post.body_html
    return render_template('edit_post.html', edit_form=edit_form)



@main.route('/blog/<int:id>', methods=['GET', 'POST'])
def blog(id):
    post = Post.query.get_or_404(id)
    '''
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = EditForm()
    form.title.data = post.title
    form.body.data = post.body
    '''
    return render_template('blog.html', post=post)


@main.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash('Invalid username or password.')
    return render_template('login.html', form=form)

@main.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            flash('Your password has been updated.')
            return redirect(url_for('.index'))
        else:
            flash('Invalid password.')
    return render_template("change_password.html", form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))


@main.route('/ckupload/', methods=['POST', 'OPTIONS'])
def ckupload():
    """CKEditor file upload"""
    error = ''
    url = ''
    callback = request.args.get("CKEditorFuncNum")

    if request.method == 'POST' and 'upload' in request.files:
        fileobj = request.files['upload']
        fname, fext = os.path.splitext(fileobj.filename)
        rnd_name = '%s%s' % (gen_rnd_filename(), fext)
        print('current_app.static_folder',current_app.static_folder)

        filepath = os.path.join(current_app.static_folder, 'upload', rnd_name)

        # 检查路径是否存在，不存在则创建
        dirname = os.path.dirname(filepath)
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except:
                error = 'ERROR_CREATE_DIR'
        elif not os.access(dirname, os.W_OK):
            error = 'ERROR_DIR_NOT_WRITEABLE'

        if not error:
            fileobj.save(filepath)
            url = url_for('static', filename='%s/%s' % ('upload', rnd_name))
    else:
        error = 'post error'

    res = """<script type="text/javascript">
  window.parent.CKEDITOR.tools.callFunction(%s, '%s', '%s');
</script>""" % (callback, url, error)

    response = make_response(res)
    response.headers["Content-Type"] = "text/html"
    return response