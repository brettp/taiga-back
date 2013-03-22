# -*- coding: utf-8 -*-

import re

from django.conf import settings
from django.db import models

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User

from greenmine.base.utils.slug import slugify_uniquely, ref_uniquely
from greenmine.base.fields import DictField
from greenmine.base.utils import iter_points
from greenmine.scrum.choices import *
from greenmine.scrum.utils import SCRUM_STATES


class Project(models.Model):
    uuid = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=250, unique=True)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField(blank=False)

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True, auto_now=True)

    owner = models.ForeignKey("auth.User", related_name="projects")
    public = models.BooleanField(default=True)
    markup = models.CharField(max_length=10, choices=MARKUP_TYPE, default='md')

    last_us_ref = models.BigIntegerField(null=True, default=0)
    last_task_ref = models.BigIntegerField(null=True, default=0)

    task_parser_re = models.CharField(max_length=1000, blank=True, null=True, default=None)
    sprints = models.IntegerField(default=1, blank=True, null=True)
    show_burndown = models.BooleanField(default=False, blank=True)
    show_burnup = models.BooleanField(default=False, blank=True)
    show_sprint_burndown = models.BooleanField(default=False, blank=True)
    total_story_points = models.FloatField(default=None, null=True)

    tags = DictField(blank=True, null=True)

    class Meta:
        permissions = (
            # global permissions
            ('list_projects', 'Can list projects'),
            ('list_my_projects', 'Can list my projects'),

            # per project permissions
            ('view_projects', 'Can view projects'),

            ('create_tasks', 'Can create tasks'),
            ('comment_tasks', 'Can comment tasks'),
            ('modify_tasks', 'Can modify tasks'),
            ('delete_task', 'Can delete tasks'),
            ('modify_owned_tasks', 'Can modify owned tasks'),
            ('modify_assigned_tasks', 'Can modify assigned tasks'),
            ('assign_tasks_to_others', 'Can assign tasks to others'),
            ('assign_tasks_to_myself', 'Can assign tasks to myself'),
            ('change_tasks_state', 'Can change the task state'),
            ('add_tasks_to_us', 'Can add tasks to a user story'),

            ('create_us', 'Can create user stories'),
            ('comment_us', 'Can comment user stories'),
            ('modify_us', 'Can modify user stories'),
            ('delete_us', 'Can delete user stories'),
            ('modify_owned_us', 'Can modify owned user stories'),
            ('add_us_to_milestones', 'Can add user stories to milestones'),

            ('create_questions', 'Can create questions'),
            ('reply_questions', 'Can reply questions'),
            ('modify_questions', 'Can modify questions'),
            ('delete_questions', 'Can delete questions'),
            ('modify_owned_questions', 'Can modify owned questions'),

            ('create_wiki_page', 'Can create wiki pages'),
            ('modify_wiki_page', 'Can modify wiki pages'),
            ('delete_wiki_page', 'Can delete wiki pages'),
            ('modify_owned_wiki_page', 'Can modify owned wiki pages'),

            ('create_documents', 'Can create documents'),
            ('modify_documents', 'Can modify documents'),
            ('delete_documents', 'Can delete documents'),
            ('modify_owned_documents', 'Can modify owned documents'),

            ('create_milestone', 'Can create milestones'),
            ('modify_milestone', 'Can modify milestones'),

            ('manage_users', 'Can manage users'),
        )

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return u"<Project %s>" % (self.slug)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify_uniquely(self.name, self.__class__)

        super(Project, self).save(*args, **kwargs)


class Milestone(models.Model):
    uuid = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=200, db_index=True)
    owner = models.ForeignKey('auth.User', related_name="milestones")
    project = models.ForeignKey('Project', related_name="milestones")

    estimated_start = models.DateField(null=True, default=None)
    estimated_finish = models.DateField(null=True, default=None)

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True, auto_now=True)
    closed = models.BooleanField(default=False)

    disponibility = models.FloatField(null=True, default=0.0)
    order = models.PositiveSmallIntegerField("Order")

    tags = DictField(blank=True, null=True)

    class Meta:
        ordering = ['-created_date']
        unique_together = ('name', 'project')

    @property
    def total_points(self):
        """
        Get total story points for this milestone.
        """

        total = sum(iter_points(self.user_stories.all()))
        return "{0:.1f}".format(total)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return u"<Milestone %s>" % (self.id)


class UserStory(models.Model):
    uuid = models.CharField(max_length=40, unique=True, blank=True)
    ref = models.CharField(max_length=200, db_index=True, null=True, default=None)
    milestone = models.ForeignKey("Milestone", blank=True,
                                  related_name="user_stories", null=True,
                                  default=None)
    project = models.ForeignKey("Project", related_name="user_stories")
    owner = models.ForeignKey("auth.User", null=True, default=None,
                              related_name="user_stories")
    priority = models.IntegerField(default=1)
    points = models.IntegerField(choices=POINTS_CHOICES, default=-1)
    status = models.CharField(max_length=50,
                              choices=SCRUM_STATES.get_us_choices(),
                              db_index=True, default="open")

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True, auto_now=True)
    tested = models.BooleanField(default=False)

    subject = models.CharField(max_length=500)
    description = models.TextField()
    finish_date = models.DateTimeField(null=True, blank=True)

    watchers = models.ManyToManyField('auth.User', related_name='us_watch',
                                      null=True)

    client_requirement = models.BooleanField(default=False)
    team_requirement = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField("Order")

    tags = DictField(blank=True, null=True)

    class Meta:
        ordering = ['order']
        unique_together = ('ref', 'project')

    def __repr__(self):
        return u"<UserStory %s>" % (self.id)

    def __unicode__(self):
        return u"{0} ({1})".format(self.subject, self.ref)

    def save(self, *args, **kwargs):
        if not self.ref:
            self.ref = ref_uniquely(self.project, self.__class__)

        super(UserStory, self).save(*args, **kwargs)


class Change(models.Model):
    change_type = models.IntegerField(choices=TASK_CHANGE_CHOICES)
    owner = models.ForeignKey('auth.User', related_name='changes')
    created_date = models.DateTimeField(auto_now_add=True)

    project = models.ForeignKey("Project", related_name="changes")

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    data = DictField(blank=True, null=True)
    tags = DictField(blank=True, null=True)


class ChangeAttachment(models.Model):
    change = models.ForeignKey("Change", related_name="attachments")
    owner = models.ForeignKey("auth.User", related_name="change_attachments")

    created_date = models.DateTimeField(auto_now_add=True)
    attached_file = models.FileField(upload_to="files/msg", max_length=500,
                                     null=True, blank=True)
    tags = DictField(blank=True, null=True)


class TaskQuerySet(models.query.QuerySet):
    def _add_categories(self, section_dict, category_id, category_element, selected):
        section_dict[category_id] = section_dict.get(category_id, {
            'element': unicode(category_element),
            'count': 0,
            'id': category_id,
            'selected': selected,
        })
        section_dict[category_id]['count'] += 1

    def _get_category(self, section_dict, order_by='element', reverse=False):
        values = section_dict.values()
        values = sorted(values, key=lambda entry: unicode(entry[order_by]))
        if reverse:
            values.reverse()
        return values

    def _get_filter_and_build_filter_dict(self, queryset, milestone_id, status_id, tags_ids, assigned_to_id, severity_id):
        task_list = list(queryset)
        milestones = {}
        status = {}
        tags = {}
        assigned_to = {}
        severity = {}

        for task in task_list:
            if task.milestone:
                selected = milestone_id and task.milestone.id == milestone_id
                self._add_categories(milestones, task.milestone.id, task.milestone.name, selected)

            selected = status_id and task.status == status_id
            self._add_categories(status, task.status, task.get_status_display(), selected)

            for tag in task.tags.all():
                selected = tags_ids and tag.id in tags_ids
                self._add_categories(tags, tag.id, tag.name, selected)

            if task.assigned_to:
                selected = assigned_to_id and task.assigned_to.id == assigned_to_id
                self._add_categories(assigned_to, task.assigned_to.id, task.assigned_to.first_name, selected)

            selected = severity_id and task.severity == int(severity_id)
            self._add_categories(severity, task.severity, task.get_severity_display(), selected)

        return{
            'list': task_list,
            'filters': {
                'milestones': self._get_category(milestones),
                'status': self._get_category(status),
                'tags': self._get_category(tags),
                'assigned_to': self._get_category(assigned_to),
                'severity': self._get_category(severity),
            }
        }

    def filter_and_build_filter_dict(self, milestone=None, status=None, tags=None, assigned_to=None, severity=None):

        queryset = self
        if milestone:
            queryset = queryset.filter(milestone=milestone)

        if status:
            queryset = queryset.filter(status=status)

        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__in=[tag])

        if assigned_to:
            queryset = queryset.filter(assigned_to=assigned_to)

        if severity:
            queryset = queryset.filter(severity=severity)

        milestone_id = milestone and milestone.id
        status_id = status
        tags_ids = tags and tags.values_list('id', flat=True)
        assigned_to_id = assigned_to and assigned_to.id
        severity_id = severity

        return self._get_filter_and_build_filter_dict(queryset, milestone_id, status_id, tags_ids, assigned_to_id, severity_id)


class TaskManager(models.Manager):
    def get_query_set(self):
        return TaskQuerySet(self.model)


class Task(models.Model):
    uuid = models.CharField(max_length=40, unique=True, blank=True)
    user_story = models.ForeignKey('UserStory', related_name='tasks', null=True, blank=True)
    last_user_story = models.ForeignKey('UserStory', null=True, blank=True)
    ref = models.CharField(max_length=200, db_index=True, null=True, default=None)
    status = models.CharField(max_length=50, choices=TASK_STATUS_CHOICES,
                              default='open')
    owner = models.ForeignKey("auth.User", null=True, default=None,
                              related_name="tasks")

    severity = models.IntegerField(choices=TASK_SEVERITY_CHOICES, default=3)
    priority = models.IntegerField(choices=TASK_PRIORITY_CHOICES, default=3)
    milestone = models.ForeignKey('Milestone', related_name='tasks', null=True,
                                  default=None, blank=True)

    project = models.ForeignKey('Project', related_name='tasks')
    type = models.CharField(max_length=10, choices=TASK_TYPE_CHOICES,
                            default='task')

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True)
    finished_date = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=50, choices=TASK_STATUS_CHOICES,
                                   null=True, blank=True)

    subject = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey('auth.User',
                                    related_name='user_storys_assigned_to_me',
                                    blank=True, null=True, default=None)

    watchers = models.ManyToManyField('auth.User', related_name='task_watch',
                                      null=True)

    changes = generic.GenericRelation(Change)
    tags = DictField(blank=True, null=True)

    objects = TaskManager()

    class Meta:
        unique_together = ('ref', 'project')

    def __unicode__(self):
        return self.subject

    @property
    def fake_status(self):
        return SCRUM_STATES.get_us_state_for_task_state(self.status)

    def save(self, *args, **kwargs):
        last_user_story = None
        if self.last_user_story != self.user_story:
            last_user_story = self.last_user_story
            self.last_user_story = self.user_story

        if self.id:
            self.modified_date = timezone.now()
            # Store information about close date of a task
            if self.last_status != self.status:
                if self.last_status in SCRUM_STATES.get_finished_task_states():
                    if self.status in SCRUM_STATES.get_unfinished_task_states():
                        self.finished_date = None
                elif self.last_status in SCRUM_STATES.get_unfinished_task_states():
                    if self.status in SCRUM_STATES.get_finished_task_states():
                        self.finished_date = timezone.now()
                self.last_status = self.status

        if not self.ref:
            self.ref = ref_uniquely(self.project, self.__class__)

        super(Task, self).save(*args, **kwargs)

        if last_user_story:
            last_user_story.update_status()

        if self.user_story:
            self.user_story.update_status()


from . import sigdispatch