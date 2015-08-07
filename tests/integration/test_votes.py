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

import pytest

from django.contrib.contenttypes.models import ContentType

from taiga.projects.votes import services as votes, models

from .. import factories as f

pytestmark = pytest.mark.django_db


def test_add_vote():
    project = f.ProjectFactory()
    project_type = ContentType.objects.get_for_model(project)
    user = f.UserFactory()
    votes_qs = models.Votes.objects.filter(content_type=project_type, object_id=project.id)

    votes.add_vote(project, user)

    assert votes_qs.get().count == 1

    votes.add_vote(project, user)  # add_vote must be idempotent

    assert votes_qs.get().count == 1


def test_remove_vote():
    user = f.UserFactory()
    project = f.ProjectFactory()
    project_type = ContentType.objects.get_for_model(project)
    votes_qs = models.Votes.objects.filter(content_type=project_type, object_id=project.id)
    f.VotesFactory(content_type=project_type, object_id=project.id, count=1)
    f.VoteFactory(content_type=project_type, object_id=project.id, user=user)

    assert votes_qs.get().count == 1

    votes.remove_vote(project, user)

    assert votes_qs.get().count == 0

    votes.remove_vote(project, user)  # remove_vote must be idempotent

    assert votes_qs.get().count == 0


def test_get_votes():
    project = f.ProjectFactory()
    project_type = ContentType.objects.get_for_model(project)
    f.VotesFactory(content_type=project_type, object_id=project.id, count=4)

    assert votes.get_votes(project) == 4


def test_get_voters():
    f.UserFactory()
    project = f.ProjectFactory()
    project_type = ContentType.objects.get_for_model(project)
    vote = f.VoteFactory(content_type=project_type, object_id=project.id)

    assert list(votes.get_voters(project)) == [vote.user]


def test_get_voted():
    f.ProjectFactory()
    project = f.ProjectFactory()
    project_type = ContentType.objects.get_for_model(project)
    vote = f.VoteFactory(content_type=project_type, object_id=project.id)

    assert list(votes.get_voted(vote.user, type(project))) == [project]


def test_get_votes_list():
    voter_user = f.UserFactory()
    viewer_user = f.UserFactory()

    project = f.ProjectFactory(is_private=False, name="Testing project")
    content_type = ContentType.objects.get_for_model(project)
    f.VoteFactory(content_type=content_type, object_id=project.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=project.id, count=1)

    user_story = f.UserStoryFactory(project=project, subject="Testing user story")
    content_type = ContentType.objects.get_for_model(user_story)
    f.VoteFactory(content_type=content_type, object_id=user_story.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=user_story.id, count=1)

    task = f.TaskFactory(project=project, subject="Testing task")
    content_type = ContentType.objects.get_for_model(task)
    f.VoteFactory(content_type=content_type, object_id=task.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=task.id, count=1)

    issue = f.IssueFactory(project=project, subject="Testing issue")
    content_type = ContentType.objects.get_for_model(issue)
    f.VoteFactory(content_type=content_type, object_id=issue.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=issue.id, count=1)

    assert len(votes.get_votes_list(voter_user, viewer_user)) == 4
    assert len(votes.get_votes_list(voter_user, viewer_user, type="project")) == 1
    assert len(votes.get_votes_list(voter_user, viewer_user, type="userstory")) == 1
    assert len(votes.get_votes_list(voter_user, viewer_user, type="task")) == 1
    assert len(votes.get_votes_list(voter_user, viewer_user, type="issue")) == 1
    assert len(votes.get_votes_list(voter_user, viewer_user, type="unknown")) == 0

    assert len(votes.get_votes_list(voter_user, viewer_user, q="issue")) == 1
    assert len(votes.get_votes_list(voter_user, viewer_user, q="unexisting text")) == 0


def test_get_votes_list_valid_info_for_project():
    voter_user = f.UserFactory()
    viewer_user = f.UserFactory()
    watcher_user = f.UserFactory()

    project = f.ProjectFactory(is_private=False, name="Testing project")
    project.watchers.add(watcher_user)
    content_type = ContentType.objects.get_for_model(project)
    vote = f.VoteFactory(content_type=content_type, object_id=project.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=project.id, count=1)

    project_vote_info = votes.get_votes_list(voter_user, viewer_user)[0]
    assert project_vote_info["type"] == "project"
    assert project_vote_info["id"] == project.id
    assert project_vote_info["ref"] == -1
    assert project_vote_info["slug"] == project.slug
    assert project_vote_info["subject"] == project.name
    assert project_vote_info["tags"] == project.tags
    assert project_vote_info["project"] == project.id
    assert project_vote_info["assigned_to"] == -1
    assert project_vote_info["total_watchers"] == 1
    assert project_vote_info["created_date"] == vote.created_date
    assert project_vote_info["project_name"] == project.name
    assert project_vote_info["project_slug"] == project.slug
    assert project_vote_info["project_is_private"] == project.is_private
    assert project_vote_info["assigned_to_username"] == None
    assert project_vote_info["assigned_to_full_name"] == None
    assert project_vote_info["assigned_to_photo"] == None
    assert project_vote_info["assigned_to_email"] == None
    assert project_vote_info["total_votes"] == 1


def test_get_votes_list_valid_info_for_not_project_types():
    voter_user = f.UserFactory()
    viewer_user = f.UserFactory()
    watcher_user = f.UserFactory()
    assigned_to_user = f.UserFactory()

    project = f.ProjectFactory(is_private=False, name="Testing project")

    factories = {
        "userstory": f.UserStoryFactory,
        "task": f.TaskFactory,
        "issue": f.IssueFactory
    }

    for object_type in factories:
        instance = factories[object_type](project=project,
            subject="Testing",
            tags=["test1", "test2"],
            assigned_to=assigned_to_user)

        instance.watchers.add(watcher_user)
        content_type = ContentType.objects.get_for_model(instance)
        vote = f.VoteFactory(content_type=content_type, object_id=instance.id, user=voter_user)
        f.VotesFactory(content_type=content_type, object_id=instance.id, count=3)

        instance_vote_info = votes.get_votes_list(voter_user, viewer_user, type=object_type)[0]
        assert instance_vote_info["type"] == object_type
        assert instance_vote_info["id"] == instance.id
        assert instance_vote_info["ref"] == instance.ref
        assert instance_vote_info["slug"] == ''
        assert instance_vote_info["subject"] == instance.subject
        assert instance_vote_info["tags"] == instance.tags
        assert instance_vote_info["project"] == instance.project.id
        assert instance_vote_info["assigned_to"] == assigned_to_user.id
        assert instance_vote_info["total_watchers"] == 1
        assert instance_vote_info["created_date"] == vote.created_date
        assert instance_vote_info["project_name"] == instance.project.name
        assert instance_vote_info["project_slug"] == instance.project.slug
        assert instance_vote_info["project_is_private"] == instance.project.is_private
        assert instance_vote_info["assigned_to_username"] == assigned_to_user.username
        assert instance_vote_info["assigned_to_full_name"] == assigned_to_user.full_name
        assert instance_vote_info["assigned_to_photo"] == ''
        assert instance_vote_info["assigned_to_email"] == assigned_to_user.email
        assert instance_vote_info["total_votes"] == 3


def test_get_votes_list_permissions():
    voter_user = f.UserFactory()
    viewer_unpriviliged_user = f.UserFactory()
    viewer_priviliged_user = f.UserFactory()

    project = f.ProjectFactory(is_private=True, name="Testing project")
    role = f.RoleFactory(project=project, permissions=["view_project", "view_us", "view_tasks", "view_issues"])
    membership = f.MembershipFactory(project=project, role=role, user=viewer_priviliged_user)
    content_type = ContentType.objects.get_for_model(project)
    f.VoteFactory(content_type=content_type, object_id=project.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=project.id, count=1)

    user_story = f.UserStoryFactory(project=project, subject="Testing user story")
    content_type = ContentType.objects.get_for_model(user_story)
    f.VoteFactory(content_type=content_type, object_id=user_story.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=user_story.id, count=1)

    task = f.TaskFactory(project=project, subject="Testing task")
    content_type = ContentType.objects.get_for_model(task)
    f.VoteFactory(content_type=content_type, object_id=task.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=task.id, count=1)

    issue = f.IssueFactory(project=project, subject="Testing issue")
    content_type = ContentType.objects.get_for_model(issue)
    f.VoteFactory(content_type=content_type, object_id=issue.id, user=voter_user)
    f.VotesFactory(content_type=content_type, object_id=issue.id, count=1)

    #If the project is private a viewer user without any permission shouldn' see any vote
    assert len(votes.get_votes_list(voter_user, viewer_unpriviliged_user)) == 0

    #If the project is private but the viewer user has permissions the votes should be accesible
    assert len(votes.get_votes_list(voter_user, viewer_priviliged_user)) == 4

    #If the project is private but has the required anon permissions the votes should be accesible by any user too
    project.anon_permissions = ["view_project", "view_us", "view_tasks", "view_issues"]
    project.save()
    assert len(votes.get_votes_list(voter_user, viewer_unpriviliged_user)) == 4
