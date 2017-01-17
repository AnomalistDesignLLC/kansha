#--
# Copyright (c) 2012-2014 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

from nagare import database
from sqlalchemy import func
import sqlalchemy as sa
from sqlalchemy.ext.associationproxy import association_proxy
from elixir import (ManyToOne, ManyToMany, OneToMany, using_options, Field, Boolean, Integer,
                    using_table_options)

from kansha.models import Entity
from kansha.card.models import DataCard
from kansha.user.models import DataUser

# Levels
NOTIFY_OFF = 0
NOTIFY_MINE = 1
NOTIFY_ALL = 2


class DataCardMembership(Entity):
    using_options(tablename='membership_cards__card')
    membership = ManyToOne('DataMembership', ondelete='cascade', required=True)
    card = ManyToOne('DataCard', ondelete='cascade', required=True)
    using_table_options(sa.UniqueConstraint('membership_id', 'card_id', name='uix_1'))


class DataMembership(Entity):
    using_options(tablename='membership')
    board = ManyToOne('DataBoard', ondelete='cascade')
    user = ManyToOne(DataUser, ondelete='cascade')
    card_memberships = OneToMany(DataCardMembership, cascade='delete, delete-orphan')
    cards = association_proxy('card_memberships', 'card')
    manager = Field(Boolean, default=False, nullable=False)
    notify = Field(Integer, default=NOTIFY_MINE)

    @classmethod
    def get_for_card(cls, card):
        return cls.query.join(DataCardMembership).filter(DataCardMembership.card == card)

    @classmethod
    def search(cls, board, user):
        return cls.get_by(board=board, user=user)  # at most one

    @classmethod
    def subscribers(cls):
        return cls.query.filter(sa.or_(DataMembership.notify == NOTIFY_ALL,
                                       DataMembership.notify == NOTIFY_MINE))

    @staticmethod
    def favorites_for(card):
        query = database.session.query(DataUser)
        query = query.join(DataMembership)
        # In the future, cards will be linked to boards directly, so demeter won't be hurt anymore
        query = query.filter(DataMembership.board == card.column.board)
        query = query.join(DataCardMembership)
        query = query.group_by(DataUser.username, DataUser.source)
        query = query.order_by(func.count(DataUser.username).desc())
        return query

    @classmethod
    def add_card_members_from_emails(cls, card, emails):
        """Provisinal: will take memberships instead of emails."""
        query = cls.query.join(DataUser).filter(DataUser.email.in_(emails),
                                                DataMembership.board == card.column.board)
        memberships = query.all()
        for membership in memberships:
            membership.card_memberships.append(DataCardMembership(card=card))
        database.session.flush()
        return memberships

    @classmethod
    def remove_card_member(cls, card, username):
        """Provisional: will take a membership instead of username."""
        membership = cls.query.join(DataUser).filter(
            DataUser.username == username,
            cls.board == card.column.board).first()
        if membership:
            card_membership = DataCardMembership.get_by(card=card, membership=membership)
            if card_membership:
                card_membership.delete()

    @classmethod
    def add_member(cls, board, user, manager=False):
        membership = cls(board=board, user=user, manager=manager)
        database.session.add(membership)
        database.session.flush()
        return membership

    @classmethod
    def remove_member(cls, board, user):
        membership = cls.get_by(board=board, user=user)
        if membership:
            membership.delete()
            database.session.flush()
