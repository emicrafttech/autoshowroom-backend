from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.bookings.availability import (
    build_vehicle_booking_availability,
    get_dealer_booking_availability,
    is_booking_slot_available,
)
from apps.bookings.models import Appointment, Booking
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle


class BookingAvailabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="prime-motors",
            name="Prime Motors",
            legal_name="Prime Motors Limited",
            area="Wuse",
            phone="+2348011111111",
            booking_availability={
                "slotLengthMinutes": 45,
                "maxBookingsPerDay": 2,
                "weeklyHours": {
                    "mon": {"enabled": True, "open": "09:00", "close": "12:00"},
                    "tue": {"enabled": True, "open": "09:00", "close": "12:00"},
                    "wed": {"enabled": True, "open": "09:00", "close": "12:00"},
                    "thu": {"enabled": True, "open": "09:00", "close": "12:00"},
                    "fri": {"enabled": True, "open": "09:00", "close": "12:00"},
                    "sat": {"enabled": False, "open": "10:00", "close": "14:00"},
                    "sun": {"enabled": False, "open": "09:00", "close": "17:00"},
                },
                "blockedDates": [],
            },
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse",
            district_slug="wuse",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="bookings@example.com",
            password="strong-pass-123",
            name="Booking Manager",
            role=StaffUser.Role.OWNER,
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="toyota-camry-2020",
            make="Toyota",
            model="Camry",
            year=2020,
            price_ngn=15000000,
            mileage_km=45000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )

    def _next_weekday(self, target_index: int) -> date:
        current = timezone.now().date()
        while current.weekday() != target_index:
            current += timedelta(days=1)
        return current

    def test_defaults_when_dealer_has_no_settings(self):
        self.dealer.booking_availability = {}
        self.dealer.save(update_fields=["booking_availability"])
        settings = get_dealer_booking_availability(self.dealer)
        self.assertEqual(settings["slotLengthMinutes"], 45)
        self.assertTrue(settings["weeklyHours"]["mon"]["enabled"])

    def test_generates_slots_within_open_hours(self):
        target_day = self._next_weekday(0)
        payload = build_vehicle_booking_availability(
            self.vehicle,
            from_date=target_day,
            to_date=target_day,
        )
        day = payload["days"][0]
        self.assertTrue(day["available"])
        self.assertEqual(len(day["slots"]), 4)
        self.assertEqual(day["slots"][0]["startAt"][11:16], "09:00")

    def test_location_booking_availability_overrides_dealer_settings(self):
        self.location.booking_availability = {
            "slotLengthMinutes": 60,
            "maxBookingsPerDay": 1,
            "weeklyHours": {
                "mon": {"enabled": True, "open": "13:00", "close": "15:00"},
            },
            "blockedDates": [],
        }
        self.location.save(update_fields=["booking_availability"])

        target_day = self._next_weekday(0)
        payload = build_vehicle_booking_availability(
            self.vehicle,
            from_date=target_day,
            to_date=target_day,
        )

        self.assertEqual(payload["slotLengthMinutes"], 60)
        self.assertEqual(payload["days"][0]["slots"][0]["startAt"][11:16], "13:00")

    def test_booked_slot_is_unavailable(self):
        target_day = self._next_weekday(0)
        slot_start = datetime.combine(
            target_day,
            datetime.strptime("09:00", "%H:%M").time(),
            tzinfo=ZoneInfo("Africa/Lagos"),
        )
        booking = Booking.objects.create(
            vehicle=self.vehicle,
            dealer=self.dealer,
            location=self.location,
            buyer_name="Ada",
            buyer_phone="+2348090000000",
            scheduled_at=slot_start,
            status=Booking.Status.PENDING,
        )
        Appointment.objects.create(
            booking=booking,
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            title="Inspection",
            scheduled_at=slot_start,
        )
        payload = build_vehicle_booking_availability(
            self.vehicle,
            from_date=target_day,
            to_date=target_day,
        )
        first_slot = payload["days"][0]["slots"][0]
        self.assertFalse(first_slot["available"])
        self.assertFalse(
            is_booking_slot_available(self.dealer, slot_start),
        )

    def test_dealer_can_mark_booking_attendance(self):
        self.client.force_authenticate(self.staff)
        slot_start = timezone.now() + timedelta(days=1)
        booking = Booking.objects.create(
            vehicle=self.vehicle,
            dealer=self.dealer,
            location=self.location,
            buyer_name="Ada",
            buyer_phone="+2348090000000",
            scheduled_at=slot_start,
            status=Booking.Status.CONFIRMED,
        )
        appointment = Appointment.objects.create(
            booking=booking,
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            title="Inspection",
            scheduled_at=slot_start,
        )

        show_response = self.client.patch(f"/v1/appointments/{appointment.id}/mark-show")
        self.assertEqual(show_response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance_status, Booking.AttendanceStatus.SHOW)
        self.assertIsNotNone(booking.attended_at)

        no_show_response = self.client.patch(f"/v1/appointments/{appointment.id}/mark-no-show")
        self.assertEqual(no_show_response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance_status, Booking.AttendanceStatus.NO_SHOW)
