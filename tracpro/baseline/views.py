from datetime import datetime
from dateutil import rrule
import pytz
import random

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponseRedirect
from django.views.generic import View

from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin

from smartmin.views import (
    SmartCRUDL, SmartCreateView, SmartDeleteView,
    SmartListView, SmartReadView, SmartUpdateView,
    SmartView
)
from smartmin.users.views import SmartFormView

from tracpro.polls.models import Answer, PollRun, Response

from .models import BaselineTerm
from .forms import BaselineTermForm, SpoofDataForm


class BaselineTermCRUDL(SmartCRUDL):
    model = BaselineTerm
    actions = ('create', 'read', 'update', 'delete', 'list', 'data_spoof', 'clear_spoof')

    class Create(OrgPermsMixin, SmartCreateView):
        form_class = BaselineTermForm
        success_url = 'id@baseline.baselineterm_read'

        def get_form_kwargs(self):
            kwargs = super(BaselineTermCRUDL.Create, self).get_form_kwargs()
            kwargs['user'] = self.request.user
            return kwargs

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'start_date', 'end_date',
                  'baseline_question', 'follow_up_question')
        link_fields = ('name')

        def derive_queryset(self, **kwargs):
            qs = BaselineTerm.get_all(self.request.org)
            qs = qs.order_by('-start_date', '-end_date')
            return qs

    class Delete(OrgObjPermsMixin, SmartDeleteView):
        cancel_url = '@baseline.baselineterm_list'

        def get_redirect_url(self):
            return reverse('baseline.baselineterm_list')

    class Update(OrgObjPermsMixin,  SmartUpdateView):
        form_class = BaselineTermForm
        delete_url = ''     # Turn off the smartmin delete button for this view
        success_url = 'id@baseline.baselineterm_read'

        def derive_queryset(self, **kwargs):
            return BaselineTerm.get_all(self.request.org)

        def get_form_kwargs(self):
            kwargs = super(BaselineTermCRUDL.Update, self).get_form_kwargs()
            kwargs['user'] = self.request.user
            return kwargs

    class Read(OrgObjPermsMixin, SmartReadView):

        def derive_queryset(self, **kwargs):
            return BaselineTerm.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(BaselineTermCRUDL.Read, self).get_context_data(**kwargs)

            region = self.request.region

            baseline_dict, baseline_dates = self.object.get_baseline(region=region)

            follow_ups, dates = self.object.get_follow_up(region=region)

            # Create a list of all dates for this poll
            # Example: date_list =  ['09/01', '09/02', '09/03', ...]
            date_list = []
            for date in dates:
                date_formatted = date.strftime('%m/%d')
                date_list.append(date_formatted)
            context['date_list'] = date_list

            # Loop through all regions to create a list of baseline values over time
            # Example: {'Kampala': {'values': [100, 100, 120, 120,...] } }
            for region in baseline_dict:
                baseline_list_all_dates = []
                baseline_list = baseline_dict[region]["values"]
                current_baseline = float(baseline_list[0])
                for date in dates:
                    if date in baseline_dates:
                        current_baseline = float(baseline_list[baseline_dates.index(date)])
                    baseline_list_all_dates.append(current_baseline)
                baseline_dict[region]["values"] = baseline_list_all_dates
            context['baseline_dict'] = baseline_dict

            # Reformat the values lists to remove the Decimal()
            # Example in:  {'Kampala': {'values': [Decimal(100), Decimal(100)...] } }
            #         out: {'Kampala': {'values': [100, 100...] } }
            answers_dict = {}
            for follow_up in follow_ups:
                answers_dict[follow_up] = {}
                answers_dict[follow_up]["values"] = [float(val) for val in follow_ups[follow_up]["values"]]
            context['answers_dict'] = answers_dict

            if len(context['answers_dict']) == 0 and len(context['baseline_dict']) == 0:
                context['error_message'] = _(
                    "No data exists for this baseline chart. You may need to select a different region.")

            return context

    class DataSpoof(OrgPermsMixin, SmartFormView):
        title = _("Baseline Term Data Spoof")
        template_name = 'baseline/baselineterm_data.html'
        form_class = SpoofDataForm
        cancel_url = '@baseline.baselineterm_list'
        success_url = '@baseline.baselineterm_list'

        def get_form_kwargs(self):
            kwargs = super(BaselineTermCRUDL.DataSpoof, self).get_form_kwargs()
            kwargs.setdefault('org', self.request.org)
            return kwargs

        def create_baseline(self, poll, date, contacts, baseline_question, baseline_minimum, baseline_maximum):
            baseline_datetime = datetime.combine(date, datetime.utcnow().time().replace(tzinfo=pytz.utc))
            baseline_pollrun = PollRun.objects.create(
                poll=poll, region=None,
                conducted_on=baseline_datetime)
            for contact in contacts:
                # Create a Response AKA FlowRun for each contact for Baseline
                response = Response.objects.create(
                    pollrun=baseline_pollrun,
                    contact=contact,
                    created_on=baseline_datetime,
                    updated_on=baseline_datetime,
                    status=Response.STATUS_COMPLETE,
                    is_active=True)
                random_answer = random.randrange(baseline_minimum, baseline_maximum)
                # Create a randomized Answer for each contact for Baseline
                Answer.objects.create(
                    response=response,
                    question=baseline_question,
                    value=random_answer,
                    submitted_on=baseline_datetime,
                    category=u'')

        def form_valid(self, form):
            baseline_question = self.form.cleaned_data['baseline_question']
            follow_up_question = self.form.cleaned_data['follow_up_question']
            contacts = self.form.cleaned_data['contacts']
            baseline_minimum = self.form.cleaned_data['baseline_minimum']
            baseline_maximum = self.form.cleaned_data['baseline_maximum']
            follow_up_minimum = self.form.cleaned_data['follow_up_minimum']
            follow_up_maximum = self.form.cleaned_data['follow_up_maximum']
            start = self.form.cleaned_data['start_date']
            end = self.form.cleaned_data['end_date']

            # Create a PollRun for each date from start to end dates for the Follow Up Poll
            for loop_count, follow_up_date in enumerate(rrule.rrule(rrule.DAILY, dtstart=start, until=end)):
                if loop_count % 7 == 0:  # On the seventh day, add another set of baseline data
                    # Create a single PollRun for the Baseline Poll
                    self.create_baseline(baseline_question.poll, follow_up_date, contacts,
                                         baseline_question, baseline_minimum, baseline_maximum)
                follow_up_datetime = datetime.combine(follow_up_date, datetime.utcnow().time().replace(tzinfo=pytz.utc))
                follow_up_pollrun = PollRun.objects.create(
                    poll=follow_up_question.poll, region=None,
                    conducted_on=follow_up_datetime)
                for contact in contacts:
                    # Create a Response AKA FlowRun for each contact for Follow Up
                    response = Response.objects.create(
                        pollrun=follow_up_pollrun,
                        contact=contact,
                        created_on=follow_up_datetime,
                        updated_on=follow_up_datetime,
                        status=Response.STATUS_COMPLETE,
                        is_active=True)
                    random_answer = random.randrange(follow_up_minimum, follow_up_maximum)
                    # Create a randomized Answer for each contact for Follow Up
                    Answer.objects.create(
                        response=response,
                        question=follow_up_question,
                        value=random_answer,
                        submitted_on=follow_up_datetime,
                        category=u'')
                loop_count += 1

            return HttpResponseRedirect(self.get_success_url())

    class ClearSpoof(OrgObjPermsMixin, SmartView, View):

        def post(self, request, *args, **kwargs):
            # Spoofed data has a NULL flow_run_id in Response
            responses = Response.objects.filter(flow_run_id__isnull=True)
            pollruns = PollRun.objects.filter(pk__in=responses.values('pollrun'))

            # This will create a cascading delete to clear out all Spoofed Poll data
            # from PollRun, Answer and Response
            pollruns.delete()

            return HttpResponseRedirect(reverse('baseline.baselineterm_list'))
