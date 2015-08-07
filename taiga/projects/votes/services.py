# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014 Anler Hernández <hello@anler.me>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.db import connection
from django.db.models import F
from django.db.transaction import atomic
from django.apps import apps
from django.contrib.auth import get_user_model

from .models import Votes, Vote


def add_vote(obj, user):
    """Add a vote to an object.

    If the user has already voted the object nothing happends, so this function can be considered
    idempotent.

    :param obj: Any Django model instance.
    :param user: User adding the vote. :class:`~taiga.users.models.User` instance.
    """
    obj_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(obj)
    with atomic():
        vote, created = Vote.objects.get_or_create(content_type=obj_type, object_id=obj.id, user=user)

        if not created:
            return

        votes, _ = Votes.objects.get_or_create(content_type=obj_type, object_id=obj.id)
        votes.count = F('count') + 1
        votes.save()
    return vote


def remove_vote(obj, user):
    """Remove an user vote from an object.

    If the user has not voted the object nothing happens so this function can be considered
    idempotent.

    :param obj: Any Django model instance.
    :param user: User removing her vote. :class:`~taiga.users.models.User` instance.
    """
    obj_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(obj)
    with atomic():
        qs = Vote.objects.filter(content_type=obj_type, object_id=obj.id, user=user)
        if not qs.exists():
            return

        qs.delete()

        votes, _ = Votes.objects.get_or_create(content_type=obj_type, object_id=obj.id)
        votes.count = F('count') - 1
        votes.save()


def get_voters(obj):
    """Get the voters of an object.

    :param obj: Any Django model instance.

    :return: User queryset object representing the users that voted the object.
    """
    obj_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(obj)
    return get_user_model().objects.filter(votes__content_type=obj_type, votes__object_id=obj.id)


def get_votes(obj):
    """Get the number of votes an object has.

    :param obj: Any Django model instance.

    :return: Number of votes or `0` if the object has no votes at all.
    """
    obj_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(obj)

    try:
        return Votes.objects.get(content_type=obj_type, object_id=obj.id).count
    except Votes.DoesNotExist:
        return 0


def get_voted(user_or_id, model):
    """Get the objects voted by an user.

    :param user_or_id: :class:`~taiga.users.models.User` instance or id.
    :param model: Show only objects of this kind. Can be any Django model class.

    :return: Queryset of objects representing the votes of the user.
    """
    obj_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(model)
    conditions = ('votes_vote.content_type_id = %s',
                  '%s.id = votes_vote.object_id' % model._meta.db_table,
                  'votes_vote.user_id = %s')

    if isinstance(user_or_id, get_user_model()):
        user_id = user_or_id.id
    else:
        user_id = user_or_id

    return model.objects.extra(where=conditions, tables=('votes_vote',),
                               params=(obj_type.id, user_id))


def get_votes_list(for_user, from_user, type=None, q=None):
    filters_sql = ""
    and_needed = False

    if type:
        filters_sql += " AND type = '{type}' ".format(type=type)

    if q:
        filters_sql += " AND to_tsvector(coalesce(subject, '')) @@ plainto_tsquery('{q}') ".format(q=q)

    sql = """
    -- BEGIN Basic info: we need to mix info from different tables and denormalize it
    SELECT entities.*,
           votes.created_date,
           projects_project.name as project_name, projects_project.slug as project_slug, projects_project.is_private as project_is_private,
           users_user.username assigned_to_username, users_user.full_name assigned_to_full_name, users_user.photo assigned_to_photo, users_user.email assigned_to_email,
           votes_votes.count total_votes
        FROM (
    	SELECT 'issue' AS type, id, ref, '' AS slug, subject, tags, project_id AS project, assigned_to_id AS assigned_to, coalesce(watchers, 0) total_watchers
    	    FROM issues_issue
    	    LEFT JOIN (SELECT issue_id, count(*) watchers FROM issues_issue_watchers GROUP BY issue_id) issues_watchers
    	    ON issues_issue.id = issues_watchers.issue_id
    	UNION
    	SELECT 'userstory'  AS type, id, ref, '' AS slug, subject, tags, project_id AS project, assigned_to_id AS assigned_to, coalesce(watchers, 0) total_watchers
    	    FROM userstories_userstory
    	    LEFT JOIN (SELECT userstory_id, count(*) watchers FROM userstories_userstory_watchers GROUP BY userstory_id) userstories_watchers
    	    ON userstories_userstory.id = userstories_watchers.userstory_id
    	UNION
    	SELECT 'task'  AS type, id, ref, '' AS slug, subject, tags, project_id AS project, assigned_to_id AS assigned_to, coalesce(watchers, 0) total_watchers
    	    FROM tasks_task
    	    LEFT JOIN (SELECT task_id, count(*) watchers FROM tasks_task_watchers GROUP BY task_id) tasks_watchers
    	    ON tasks_task.id = tasks_watchers.task_id
    	UNION
    	SELECT 'project'  AS type, id, -1 AS ref, slug, name, tags, id AS project, -1 AS assigned_to, coalesce(watchers, 0) total_watchers
    	    FROM projects_project
    	    LEFT JOIN (SELECT project_id, count(*) watchers FROM projects_project_watchers GROUP BY project_id) projects_watchers
    	    ON projects_project.id = projects_watchers.project_id
        ) as entities
    -- END Basic info

    -- BEGIN Project info
    LEFT JOIN projects_project
        ON (entities.project = projects_project.id)
    -- END Project info

    -- BEGIN Assigned to user info
    LEFT JOIN users_user
        ON (assigned_to = users_user.id)
    -- END Assigned to user info

    -- BEGIN Votes info
    INNER JOIN (
        SELECT votes_vote.id, votes_vote.object_id, votes_vote.content_type_id, votes_vote.user_id, votes_vote.created_date,  django_content_type.model
            FROM votes_vote
            INNER JOIN django_content_type ON (votes_vote.content_type_id = django_content_type.id)
            WHERE user_id = {for_user_id}
        ) votes
        ON (entities.id = votes.object_id AND entities.type = votes.model)

    INNER JOIN votes_votes
        ON (votes.object_id = votes_votes.object_id AND votes.content_type_id = votes_votes.content_type_id)
    -- END Votes info

    -- BEGIN Permissions checking
    LEFT JOIN projects_membership
        -- Here we check the memberbships from the user requesting the info
        ON (projects_membership.user_id = {from_user_id} AND projects_membership.project_id = entities.project)

    LEFT JOIN users_role
        ON (entities.project = users_role.project_id AND users_role.id =  projects_membership.role_id)

    WHERE
        -- public project
        (
            projects_project.is_private = false
            OR(
                -- private project where the view_ permission is included in the user role for that project or in the anon permissions
                projects_project.is_private = true
                AND(
                    (entities.type = 'issue' AND 'view_issues' = ANY (array_cat(users_role.permissions, projects_project.anon_permissions)))
                    OR (entities.type = 'task' AND 'view_tasks' = ANY (array_cat(users_role.permissions, projects_project.anon_permissions)))
                    OR (entities.type = 'userstory' AND 'view_us' = ANY (array_cat(users_role.permissions, projects_project.anon_permissions)))
                    OR (entities.type = 'project' AND 'view_project' = ANY (array_cat(users_role.permissions, projects_project.anon_permissions)))
                )
        ))
    -- END Permissions checking
        {filters_sql}

    ORDER BY votes.created_date;
    """
    from_user_id = -1
    if not from_user.is_anonymous():
        from_user_id = from_user.id

    sql = sql.format(for_user_id=for_user.id, from_user_id=from_user_id, filters_sql=filters_sql)

    cursor = connection.cursor()
    cursor.execute(sql)

    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]
