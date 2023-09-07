import os
import caldav
import requests

from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime, date, timedelta


@dataclass
class RequestParams():
    oid: int
    receiver_type: int
    from_date: date
    to_date: date
    api_url: str


@dataclass
class Lesson():
    starts_at: datetime
    ends_at: datetime
    title: str
    kind: str
    group_num: str
    auditorium: str


def get_week(today: datetime) -> {date, date}:
    start = today.date() - timedelta(today.weekday())
    end = start + timedelta(6)
    return start, end


def formated_date(d: date) -> str:
    return d.strftime("%Y.%m.%d")


def get_timetable(params: RequestParams) -> list[dict]:
    match params.receiver_type:
        case 1:
            payload = {
                "fromdate": params.from_date,
                "todate": params.to_date,
                "receiverType": params.receiver_type,
                "lecturerOid": params.oid
            }
        case 3:
            payload = {
                "fromdate": params.from_date,
                "todate": params.to_date,
                "receiverType": params.receiver_type,
                "groupOid": params.oid
            }
        case _:
            raise Exception("Failed!")

    resp = requests.get(
        url=params.api_url + "personlessons",
        params=payload
    )

    if resp.status_code != 200:
        raise Exception("Failed")

    return resp.json()


def parse_lesson(c: dict) -> Lesson:
    fmt = "%Y.%m.%d %H:%M"
    lesson = Lesson(
        starts_at=datetime.strptime(f"{c['date']} {c['beginLesson']}", fmt),
        ends_at=datetime.strptime(f"{c['date']} {c['endLesson']}", fmt),
        title=" ".join(
            [w[:3] for w in c["discipline"].split()]
        ),
        auditorium=c["auditorium"],
        kind=c["kindOfWork"][:3],
        group_num=""
    )

    if len(c["listGroups"]) != 0:
        lesson.group_num = c["listGroups"][0]["group"]
    elif c["stream"]:
        lesson.group_num = c["stream"]
    elif c["subGroup"]:
        lesson.group_num = c["subGroup"]

    return lesson


def get_lessons(params: RequestParams) -> list[Lesson]:
    classes = get_timetable(params=params)
    return [parse_lesson(c) for c in classes]


def update_calendar(
        params: RequestParams,
        caldav_url: str,
        calendar_number: int,
        login: str,
        passwd: str
) -> None:

    lessons = get_lessons(params)

    if len(lessons) == 0:
        raise Exception("hui")

    with caldav.DAVClient(
        url=caldav_url,
        username=login,
        password=passwd
    ) as client:

        principal = client.principal()
        calendars = principal.calendars()

        if len(calendars) >= calendar_number:
            for lsn in lessons:
                match params.receiver_type:
                    case 1:
                        summary = f"{lsn.kind} {lsn.title} {lsn.auditorium} \
                            {lsn.group_num}"
                    case 3:
                        summary = f"{lsn.kind} {lsn.title} {lsn.auditorium}"
                    case _:
                        raise Exception("Ooops...")

                calendars[calendar_number].save_event(
                    dtstart=lsn.starts_at,
                    dtend=lsn.ends_at,
                    summary=summary)


if __name__ == "__main__":
    parser = ArgumentParser(prog="Galaktika timetable syncronizer")

    parser.add_argument(
        "-w", "--week", type=str,
        help="Week to sync: current or next?",
        choices=["next", "current"],
        required=True
    )

    parser.add_argument(
        "-i", "--id", type=int,
        help="Identificator of your lecturer or group",
        required=True
    )

    parser.add_argument(
        "-t", "--type", type=int,
        help="Type of timetable receiver: 1 - lecturer, 3 - group",
        choices=[1, 3],
        required=True
    )

    parser.add_argument(
        "-n", "--number", type=int,
        help="Calendar number to be synced, default 0",
        default=0
    )

    args = parser.parse_args()

    if args:
        if args.week == "current":
            dt = datetime.now()
        elif args.week == "next":
            dt = datetime.now() + timedelta(7)

        from_date, to_date = get_week(dt)

        params = RequestParams(
            oid=args.id,
            receiver_type=args.type,
            from_date=from_date,
            to_date=to_date,
            api_url=os.environ.get("API_URL")
        )

        update_calendar(
            params=params,
            caldav_url=os.environ.get("CALDAV_URL"),
            calendar_number=args.number,
            login=os.environ.get("LOGIN"),
            passwd=os.environ.get("PASSWORD")
        )
