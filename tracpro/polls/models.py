from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from tracpro.contacts.models import Contact


class Poll(models.Model):
    """
    Corresponds to a RapidPro Flow
    """
    flow_uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='polls')

    name = models.CharField(max_length=64, verbose_name=_("Name"))  # taken from flow name

    is_active = models.BooleanField(default=True, help_text="Whether this item is active")

    @classmethod
    def create(cls, org, name, flow_uuid):
        return cls.objects.create(org=org, name=name, flow_uuid=flow_uuid)

    @classmethod
    def sync_with_flows(cls, org, flow_uuids):
        # de-activate polls whose flows were not selected
        org.polls.exclude(flow_uuid=flow_uuids).update(is_active=False)

        # fetch flow details
        flows_by_uuid = {flow.uuid: flow for flow in org.get_temba_client().get_flows()}

        for flow_uuid in flow_uuids:
            flow = flows_by_uuid[flow_uuid]

            poll = org.polls.filter(flow_uuid=flow.uuid).first()
            if poll:
                poll.name = flow.name
                poll.is_active = True
                poll.save()
            else:
                poll = cls.create(org, flow.name, flow.uuid)

            poll.update_questions_from_rulesets(flow.rulesets)

    def update_questions_from_rulesets(self, rulesets):
        # de-activate any existing questions no longer included
        self.questions.exclude(ruleset_uuid=[r.uuid for r in rulesets]).update(is_active=False)

        for ruleset in rulesets:
            question = self.questions.filter(ruleset_uuid=ruleset.uuid).first()
            if question:
                question.text = ruleset.label
                question.is_active = True
                question.save()
            else:
                Question.create(self, ruleset.label, ruleset.uuid)

    @classmethod
    def get_all(cls, org):
        return org.polls.filter(is_active=True)

    def get_questions(self):
        return self.questions.filter(is_active=True)

    def __unicode__(self):
        return self.name


class Question(models.Model):
    """
    Corresponds to RapidPro RuleSet
    """
    ruleset_uuid = models.CharField(max_length=36, unique=True)

    poll = models.ForeignKey(Poll, related_name='questions')

    text = models.CharField(max_length=64)  # taken from RuleSet label

    show_with_contact = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True, help_text="Whether this item is active")

    @classmethod
    def create(cls, poll, text, ruleset_uuid):
        return cls.objects.create(poll=poll, text=text, ruleset_uuid=ruleset_uuid)


class Issue(models.Model):
    """
    Corresponds to a RapidPro FlowStart
    """
    flow_start_id = models.IntegerField(null=True)

    poll = models.ForeignKey(Poll, related_name='issues')

    conducted_on = models.DateTimeField(help_text=_("When the poll was conducted"))

    @classmethod
    def create(cls, poll, conducted_on, flow_start_id):
        return cls.objects.create(poll=poll, conducted_on=conducted_on, flow_start_id=flow_start_id)

    @classmethod
    def get_or_create(cls, poll):
        # TODO need a way to associate flow runs that may or may not have flow starts. For now just get last issue.
        last = poll.issues.order_by('-conducted_on').first()
        if last:
            return last

        return Issue.create(poll, timezone.now(), None)


class Response(models.Model):
    """
    Corresponds to RapidPro FlowRun
    """
    flow_run_id = models.IntegerField(unique=True)

    issue = models.ForeignKey(Issue, related_name='responses')

    contact = models.ForeignKey(Contact, related_name='responses')

    created_on = models.DateTimeField(help_text=_("When this response was created"))

    updated_on = models.DateTimeField(help_text=_("When the last activity on this response was"))

    is_complete = models.BooleanField(default=None, help_text=_("Whether this response is complete"))

    @classmethod
    def get_or_create(cls, org, run, poll=None):
        """
        Gets or creates a response from a Temba flow run. If response is not up-to-date with provided run, then it is
        updated.
        """
        response = Response.objects.filter(issue__poll__org=org, flow_run_id=run.id).first()
        run_updated_on = cls.get_run_updated_on(run)

        # if there is an up-to-date existing response, return it
        if response and response.updated_on == run_updated_on:
            return response

        if not poll:
            poll = Poll.get_all(org).get(flow_uuid=run.flow)

        issue = Issue.get_or_create(poll)
        contact = Contact.get_or_fetch(poll.org, uuid=run.contact)
        questions = poll.get_questions()

        # organize values by ruleset UUID
        valuesets_by_ruleset = {valueset.node: valueset for valueset in run.values}
        valuesets_by_question = {q: valuesets_by_ruleset.get(q.ruleset_uuid, None) for q in questions}

        completed_questions = sum(1 for v in valuesets_by_question.values() if v is not None)
        is_complete = completed_questions == len(questions)

        if response:
            # clear existing answers which will be replaced
            response.answers.all().delete()

            response.updated_on = run_updated_on
            response.is_complete = is_complete
            response.save(update_fields=('updated_on', 'is_complete'))
        else:
            response = Response.objects.create(flow_run_id=run.id, issue=issue, contact=contact,
                                               created_on=run.created_on, updated_on=run_updated_on,
                                               is_complete=is_complete)

        # convert valuesets to answers
        for question, valueset in valuesets_by_question.iteritems():
            if valueset:
                Answer.objects.create(response=response, question=question,
                                      category=valueset.category, value=valueset.value, submitted_on=valueset.time)

        return response

    @classmethod
    def get_run_updated_on(cls, run):
        # find the valueset with the latest time
        last_value_on = None
        for valueset in run.values:
            if not last_value_on or valueset.time > last_value_on:
                last_value_on = valueset.time

        return last_value_on if last_value_on else run.created_on


class Answer(models.Model):
    """
    Corresponds to RapidPro FlowStep
    """
    response = models.ForeignKey(Response, related_name='answers')

    question = models.ForeignKey(Question, related_name='answers')

    category = models.CharField(max_length=36, null=True)

    value = models.CharField(max_length=640, null=True)

    submitted_on = models.DateTimeField(help_text=_("When this answer was submitted"))
