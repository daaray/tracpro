from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin

from django.utils.translation import ugettext_lazy as _

from smartmin.users.views import SmartTemplateView

from tracpro.polls.models import Poll
from tracpro.baseline.models import BaselineTerm
from tracpro.baseline.utils import chart_baseline


class HomeView(OrgPermsMixin, SmartTemplateView):
    """TracPro homepage"""

    title = _("Home")
    template_name = 'home/home.html'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        context['polls'] = Poll.objects.active().by_org(self.request.org).order_by('name')
        # Loop through all baseline terms, until we find one with data
        baselineterms = BaselineTerm.objects.by_org(self.request.org).order_by('-end_date')
        for baselineterm in baselineterms:
            data_found = baselineterm.check_for_data(self.request.data_regions)
            if data_found:
                (follow_up_list, baseline_list, all_regions, date_list,
                 baseline_mean, baseline_std, follow_up_mean, follow_up_std,
                 baseline_response_rate, follow_up_response_rate) = chart_baseline(
                    baselineterm=baselineterm, regions=self.request.data_regions, region_selected=None)
                context['all_regions'] = all_regions
                context['date_list'] = date_list
                context['baseline_list'] = baseline_list
                context['follow_up_list'] = follow_up_list
                context['baselineterm'] = baselineterm
                break  # Found our baseline chart with data, send it back to the view

        # Return top 5 baseline terms only
        context['baselineterms'] = baselineterms[0:5]

        return context
