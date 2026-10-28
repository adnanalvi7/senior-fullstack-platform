"""
WebSocket authorization and delivery, end to end through the ASGI app (ticket middleware,
consumer, channel layer) — not just the broadcast helper.
"""
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.approvals.consumers import broadcast_analytics_update
from apps.approvals.services import ApprovalWorkflowService
from apps.properties.models import Property
from apps.projects.models import Project
from common.ws_auth import issue_ws_ticket
from config.asgi import application


class TestRealtime(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A", slug="a")
        self.org2 = Organization.objects.create(name="B", slug="b")
        self.p1 = Property.objects.create(org=self.org, name="1", code="1")
        self.p2 = Property.objects.create(org=self.org, name="2", code="2")
        self.pb = Property.objects.create(org=self.org2, name="b", code="b")
        self.admin = User.objects.create_user(email="admin@a.com", password="password", org=self.org, role="org_admin")
        self.pm1 = User.objects.create_user(email="pm1@a.com", password="password", org=self.org, role="property_manager")
        UserPropertyAccess.objects.create(user=self.pm1, property=self.p1)
        self.pm2 = User.objects.create_user(email="pm2@a.com", password="password", org=self.org, role="property_manager")
        UserPropertyAccess.objects.create(user=self.pm2, property=self.p2)
        self.approver = User.objects.create_user(email="ap@a.com", password="password", org=self.org, role="approver")
        UserPropertyAccess.objects.create(user=self.approver, property=self.p1)
        self.admin_b = User.objects.create_user(email="admin@b.com", password="password", org=self.org2, role="org_admin")

    def projects(self, n):
        return [Project.objects.create(org=self.org, property=self.p1, title=f"t{i}", category="HVAC",
                                       fiscal_period="FY2025", budget_amount="1.00", status="submitted") for i in range(n)]

    async def connect(self, user=None, ticket=None):
        if ticket is None and user is not None:
            ticket = await database_sync_to_async(issue_ws_ticket)(user)
        path = '/ws/approvals/' + (f'?ticket={ticket}' if ticket else '')
        comm = WebsocketCommunicator(application, path)
        connected, _ = await comm.connect()
        if connected:
            await comm.receive_json_from()  # 'connected' ack
        return comm, connected

    async def received_project_ids(self, comm):
        ids = []
        while not await comm.receive_nothing(timeout=0.3):
            msg = await comm.receive_json_from()
            if msg['type'] == 'approval_update':
                ids.append(msg['data']['project_id'])
        return ids

    def test_handshake_requires_valid_ticket(self):
        async def run():
            for ticket in (None, 'garbage', 'eyJhbGciOiJIUzI1NiJ9.e30.x'):
                comm, ok = await self.connect(ticket=ticket or '')
                self.assertFalse(ok, ticket)
        async_to_sync(run)()

    def test_scoped_delivery_survives_repeated_events_and_rollup_jobs(self):
        targets = self.projects(3)

        async def run():
            socks = {}
            for name, user in (('admin', self.admin), ('pm1', self.pm1), ('pm2', self.pm2), ('admin_b', self.admin_b)):
                socks[name], ok = await self.connect(user)
                self.assertTrue(ok)
            for project in targets:  # each approval also runs the (eager) rollup job + its invalidation
                await database_sync_to_async(ApprovalWorkflowService.execute_transition)(project.id, self.approver, 'manager_approve')
            got = {name: await self.received_project_ids(c) for name, c in socks.items()}
            for c in socks.values():
                await c.disconnect()
            return got

        got = async_to_sync(run)()
        expected = [p.id for p in targets]
        self.assertEqual(got['admin'], expected)
        self.assertEqual(got['pm1'], expected)
        self.assertEqual(got['pm2'], [])      # same org, not entitled to property 1
        self.assertEqual(got['admin_b'], [])  # other tenant

    def test_revoked_entitlement_stops_delivery_without_reconnect(self):
        project, = self.projects(1)

        async def run():
            comm, ok = await self.connect(self.pm1)
            self.assertTrue(ok)
            await database_sync_to_async(UserPropertyAccess.objects.filter(user=self.pm1).delete)()
            # force the consumer to re-read entitlements on the next event
            from apps.approvals import consumers
            original = consumers.ENTITLEMENT_TTL_SECONDS
            consumers.ENTITLEMENT_TTL_SECONDS = -1
            try:
                await database_sync_to_async(ApprovalWorkflowService.execute_transition)(project.id, self.approver, 'manager_approve')
                ids = await self.received_project_ids(comm)
            finally:
                consumers.ENTITLEMENT_TTL_SECONDS = original
            await comm.disconnect()
            return ids

        self.assertEqual(async_to_sync(run)(), [])

    def test_analytics_update_and_heartbeat(self):
        async def run():
            comm, ok = await self.connect(self.pm1)
            await database_sync_to_async(broadcast_analytics_update)(self.org.id, self.p1.id, 'FY2025')
            msg = await comm.receive_json_from()
            await comm.send_json_to({'type': 'ping', 'ts': 1})
            pong = await comm.receive_json_from()
            await comm.disconnect()
            return msg, pong

        msg, pong = async_to_sync(run)()
        self.assertEqual(msg['type'], 'analytics_update')
        self.assertEqual(msg['data']['property_id'], self.p1.id)
        self.assertEqual(pong, {'type': 'pong', 'ts': 1})
