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

from django.apps import apps


def attach_is_watched_to_queryset(user, queryset, as_field="is_watched"):
    """Attach is_watched boolean to each object of the queryset.

    :param user: A users.User object model
    :param queryset: A Django queryset object.
    :param as_field: Attach the boolean as an attribute with this name.

    :return: Queryset object with the additional `as_field` field.
    """
    model = queryset.model
    model_name = model._meta.model_name
    type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(model)
    table_name = model._meta.db_table

    sql = ("""SELECT CASE WHEN (SELECT count(*)
                                  FROM {table_name}_watchers
                                 WHERE {table_name}_watchers.{model_name}_id = {table_name}.id
                                   AND user_id = {user_id}) > 0
                          THEN TRUE
                          ELSE FALSE
                     END""")
    sql = sql.format(table_name=table_name, user_id=user.id, model_name=model_name)
    qs = queryset.extra(select={as_field: sql})
    return qs
