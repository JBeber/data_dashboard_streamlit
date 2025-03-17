import os
from datetime import datetime
import streamlit as st
from streamlit_calendar import calendar

st.set_page_config(page_title="VV Events Calendar", 
                   page_icon="📆", 
                   layout="wide")

st.markdown(
    "# VV Events Calendar"
)

with open('events.txt') as file:
    contents = file.read()
    calendar_events = contents.split("},")

mode = st.selectbox(
    "Calendar Mode:",
    (
        "Month",
        "Week",
        "Day",
        "List",
    ),
)

class NewEvent:
    def __init__(self, name, st_dt, en_dt,
                 allDay, st_tm, en_tm):
        self.name = name
        self.st_dt = st_dt
        self.en_dt = en_dt
        self.allDay = allDay
        self.st_tm = st_tm
        self.en_tm = en_tm



def save_new_event(event):    
    if event.st_tm is not None:
        start = datetime.combine(event.st_dt, event.st_tm).isoformat(timespec='seconds')
        end = datetime.combine(event.en_dt, event.en_tm).isoformat(timespec='seconds')
    else:
        start = event.st_dt.isoformat()
        end = event.en_dt.isoformat()

    calendar_events.append(
        {
            "title": event.name,
            "color": "#FF6C6C",
            "start": start,
            "end": end,
            "allDay": event.allDay,
        },
    )
    
with st.popover('Add Event'):
    event_name = st.text_input('Event Name')

    event_start_date = st.date_input("Start Date")
    event_end_date = st.date_input("End Date")

    if event_start_date == event_end_date:
        allday_event = st.checkbox('All day event?')
    else:
        allday_event = True

    if not allday_event:
        event_start_time = st.time_input('Start Time')
        event_end_time = st.time_input('End Time')
    else:
        event_start_time = event_end_time = None

    new_event = NewEvent(event_name, event_start_date, event_end_date,
                         allday_event, event_start_time, event_end_time)

    st.button('Save', on_click=save_new_event, args=(new_event,))

# Resources (e.g. specific rooms, equipment, or personnel
# are not needed at this time, but can be specified later
# should the need arise.
#  
# calendar_resources = [
#     {"id": "a", "building": "Building A", "title": "Room A"},
#     {"id": "b", "building": "Building A", "title": "Room B"},
#     {"id": "c", "building": "Building B", "title": "Room C"},
#     {"id": "d", "building": "Building B", "title": "Room D"},
#     {"id": "e", "building": "Building C", "title": "Room E"},
#     {"id": "f", "building": "Building C", "title": "Room F"},
# ]

calendar_options = {
    "editable": "true",
    "navLinks": "true",
    "selectable": "true",
    "height": 750
}

if mode == "Month":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "today"; defaults to today's date when not specified
        "initialView": "dayGridMonth",
    }
elif mode == "Week":
    calendar_options = {
        **calendar_options,
        "initialView": "timeGridWeek",
    }
elif mode == "Day":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "2023-07-01",
        "initialView": "timelineDay",
    }
elif mode == "List":
    calendar_options = {
        **calendar_options,
        # "initialDate": "2023-07-01",
        "initialView": "listMonth",
    }

state = calendar(
    events=st.session_state.get("events", calendar_events),
    options=calendar_options,
    custom_css="""
    .fc-event-past {
        opacity: 0.8;
    }
    .fc-event-time {
        font-style: italic;
    }
    .fc-event-title {
        font-weight: 700;
    }
    .fc-toolbar-title {
        font-size: 2rem;
    }
    """,
    key=mode,
)

if state.get("eventsSet") is not None:
    st.session_state["events"] = state["eventsSet"]

st.write(state)

# st.markdown("## API reference")
# st.help(calendar)