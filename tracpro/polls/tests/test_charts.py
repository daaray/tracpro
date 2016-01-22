from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse
from django.db.models import Q

from tracpro.test import factories
from tracpro.test.cases import TracProTest

from .. import charts
from .. import models


class PollChartTest(TracProTest):

    def setUp(self):
        super(PollChartTest, self).setUp()

        self.org = factories.Org()

        self.poll = factories.Poll(org=self.org)

        self.question1 = factories.Question(
            poll=self.poll, question_type=models.Question.TYPE_MULTIPLE_CHOICE)
        self.question2 = factories.Question(
            poll=self.poll, question_type=models.Question.TYPE_OPEN)
        self.question3 = factories.Question(
            poll=self.poll, question_type=models.Question.TYPE_NUMERIC)

        self.pollrun = factories.UniversalPollRun(poll=self.poll)
        self.pollruns = models.PollRun.objects.filter(pk=self.pollrun.pk)

        self.response1 = factories.Response(
            pollrun=self.pollrun, status=models.Response.STATUS_COMPLETE)
        factories.Answer(
            response=self.response1, question=self.question1,
            value="4.00000", category="1 - 5")
        factories.Answer(
            response=self.response1, question=self.question2,
            value="It's very rainy", category="All Responses")
        factories.Answer(
            response=self.response1, question=self.question3,
            value="4.00000", category="1 - 5")

        self.response2 = factories.Response(
            pollrun=self.pollrun, status=models.Response.STATUS_COMPLETE)
        factories.Answer(
            response=self.response2, question=self.question1,
            value="3.00000", category="1 - 5")
        factories.Answer(
            response=self.response2, question=self.question2,
            value="rainy and rainy", category="All Responses")
        factories.Answer(
            response=self.response2, question=self.question3,
            value="3.00000", category="1 - 5")

        self.response3 = factories.Response(
            pollrun=self.pollrun, status=models.Response.STATUS_COMPLETE)
        factories.Answer(
            response=self.response3, question=self.question1,
            value="8.00000", category="6 - 10")
        factories.Answer(
            response=self.response3, question=self.question2,
            value="Sunny sunny", category="All Responses")
        factories.Answer(
            response=self.response3, question=self.question3,
            value="8.00000", category="6 - 10")

    def test_multiple_pollruns_multiple_choice(self):
        answers = models.Answer.objects.filter(question=self.question1)
        data = charts.multiple_pollruns_multiple_choice(answers, self.pollruns, self.question1)

        self.assertEqual(
            data['dates'],
            [self.pollrun.conducted_on.strftime('%Y-%m-%d')])
        self.assertEqual(data['series'], [
            {'name': '1 - 5',
             'data': [{'y': 2, 'url': reverse('polls.pollrun_read', args=[self.pollrun.pk])}]},
            {'name': '6 - 10',
             'data': [{'y': 1, 'url': reverse('polls.pollrun_read', args=[self.pollrun.pk])}]},
        ])

    def test_multiple_pollruns_open(self):
        answers = models.Answer.objects.filter(question=self.question2)
        data = charts.multiple_pollruns_open(answers, self.pollruns, self.question2)
        self.assertEqual(data, [
            {"text": "rainy", "weight": 3},
            {"text": "sunny", "weight": 2},
        ])

    def test_multiple_pollruns_numeric(self):
        answers = models.Answer.objects.filter(question=self.question3)
        data = charts.multiple_pollruns_numeric(answers, self.pollruns, self.question3)

        # Answers are 4, 3 and 8 for a single date

        # Single item for single date: sum = 4 + 3 + 8 = 15
        # URL points to pollrun detail page for this date
        self.assertEqual(
            data['sum'],
            [{"y": 15.0, "url": reverse('polls.pollrun_read', args=[self.pollrun.pk])}])

        # Single item for single date: average = (4 + 3 + 8)/3 = 5
        # URL points to pollrun detail page for this date
        self.assertEqual(
            data['average'],
            [{"y": 5.0, "url": reverse('polls.pollrun_read', args=[self.pollrun.pk])}])

        # Set all responses to complete in setUp()
        # Response rate = 100%
        # URL points to participation tab
        self.assertEqual(
            data['response-rate'],
            [{"y": 100.0, "url": reverse('polls.pollrun_participation', args=[self.pollrun.pk])}])

        # Today's date
        self.assertEqual(
            data['dates'],
            [self.pollrun.conducted_on.strftime('%Y-%m-%d')])

        # Mean, Standard Dev, response rate avg, pollrun list
        self.assertEqual(
            self.question3.answer_mean,
            5.0)
        self.assertEqual(
            self.question3.answer_stdev,
            0.0)
        self.assertEqual(
            self.question3.response_rate_average,
            100.0)

        # Set one of the responses to partial, changing the response rate
        self.response1.status = models.Response.STATUS_PARTIAL
        self.response1.save()

        data = charts.multiple_pollruns_numeric(answers, self.pollruns, self.question3)

        # 2 complete responses, 1 partial response
        # Response rate = 66.67%
        self.assertEqual(
            data['response-rate'],
            [{"y": 66.67, "url": reverse('polls.pollrun_participation', args=[self.pollrun.pk])}])
        self.assertEqual(
            self.question3.response_rate_average,
            66.67)

    def test_single_pollrun_multiple_choice(self):
        answers = models.Answer.objects.filter(question=self.question1)
        data = charts.single_pollrun_multiple_choice(answers, self.pollrun)

        self.assertEqual(
            data['data'],
            [2, 1])
        self.assertEqual(
            data['categories'],
            [u'1 - 5', u'6 - 10'])

    def test_single_pollrun_open(self):
        answer_filters = Q(response__is_active=True)
        (chart_type,
         chart_data,
         chart_data_exists,
         answer_avg,
         response_rate,
         stdev) = charts.single_pollrun(self.pollrun, self.question2, answer_filters)
        chart_data = json.loads(chart_data)

        self.assertEqual(
            chart_type,
            'open-ended')
        self.assertEqual(
            chart_data_exists,
            True)
        self.assertEqual(
            chart_data[0],
            {'text': 'rainy', 'weight': 3})
        self.assertEqual(
            len(chart_data),
            2)

    def test_single_pollrun_numeric(self):
        # Answers for question 3 = 8, 3 and 4
        # Average = 5, Response Rate = 100%, STDEV = 2.16
        answer_filters = Q(response__is_active=True)
        (chart_type,
         chart_data,
         chart_data_exists,
         answer_avg,
         response_rate,
         stdev) = charts.single_pollrun(self.pollrun, self.question3, answer_filters)
        chart_data = json.loads(chart_data)

        self.assertEqual(
            chart_type,
            'bar')
        self.assertEqual(
            chart_data_exists,
            True)
        self.assertEqual(
            answer_avg,
            5)
        self.assertEqual(
            response_rate,
            100)
        self.assertEqual(
            stdev,
            2.16)
