# runapscheduler.py
import logging

from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from pathlib import Path
from datetime import datetime
from ... import models as m


logger = logging.getLogger(__name__)


def test_every_minute():
    with Path("/tmp/test_every_minute.txt").open("a") as f:
        f.write(f"test_every_minute ran at {datetime.now()}\n")


# The `close_old_connections` decorator ensures that database connections, that have become
# unusable or are obsolete, are closed before and after our job has run.
@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    This job deletes APScheduler job execution entries older than `max_age` from the database.
    It helps to prevent the database from filling up with old historical records that are no
    longer useful.
  
    :param max_age: The maximum length of time to retain historical job execution records.
                    Defaults to 7 days.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs APScheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        if False:
            scheduler.add_job(
                test_every_minute,
                trigger=CronTrigger(minute="*", second="42"),  # Every 10 seconds
                id="test_every_minute",  # The `id` assigned to each job MUST be unique
                max_instances=1,
                replace_existing=True,
            )
            logger.info("Added job 'test_every_minute'")

        if True:
            scheduler.add_job(
                m.Delivery.freeze_overdue_deliveries,
                trigger=CronTrigger(day="*", hour="00", minute="10"),  # Every day at 00:10AM
                id="auto_freeze_deliveries",  # The `id` assigned to each job MUST be unique
                max_instances=1,
                replace_existing=True,
            )
            logger.info("Added job 'auto_freeze_deliveries'")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),  # Midnight on Monday, before start of the next work week.
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "Added weekly job: 'delete_old_job_executions'."
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")

