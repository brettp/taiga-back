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

from taiga.base.api import serializers
from taiga.base.fields import TagsField

from taiga.users.models import User
from taiga.users.services import get_photo_or_gravatar_url

from collections import namedtuple


class VoterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'full_name')


class VotedContentSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.IntegerField()
    ref = serializers.IntegerField()
    slug = serializers.CharField()
    subject = serializers.CharField()
    tags = TagsField(default=[])
    project = serializers.IntegerField()
    assigned_to = serializers.IntegerField()
    total_watchers = serializers.IntegerField()

    voting = serializers.SerializerMethodField("get_voting")
    watching = serializers.SerializerMethodField("get_watching")

    created_date = serializers.DateTimeField()

    project_name = serializers.CharField()
    project_slug = serializers.CharField()
    project_is_private = serializers.CharField()

    assigned_to_username = serializers.CharField()
    assigned_to_full_name = serializers.CharField()
    assigned_to_photo = serializers.SerializerMethodField("get_photo")

    total_votes = serializers.IntegerField()

    def __init__(self, *args, **kwargs):
        # Don't pass the extra ids args up to the superclass
        self.user_votes  = kwargs.pop("user_votes", {})
        self.user_watching = kwargs.pop("user_watching", {})

        # Instantiate the superclass normally
        super(VotedContentSerializer, self).__init__(*args, **kwargs)

    def get_voting(self, obj):
        return obj["id"] in self.user_votes.get(obj["type"], [])

    def get_watching(self, obj):
        return obj["id"] in self.user_watching.get(obj["type"], [])

    def get_photo(self, obj):
        UserData = namedtuple("UserData", ["photo", "email"])
        user_data = UserData(photo=obj["assigned_to_photo"], email=obj.get("assigned_to_email") or "")
        return get_photo_or_gravatar_url(user_data)
