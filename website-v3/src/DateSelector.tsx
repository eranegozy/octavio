import React, { useState } from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "./DateSelector.css";

export default function DateSelector({notificationDates}: {notificationDates: Array<Date>}) {
  const [startDate, setStartDate] = useState(new Date());


  const hasNotification = (date) => {
    const dateString = date.toISOString().split("T")[0];
    return notificationDates.includes(dateString);
  };

  const renderDay = (day, date) => {
    const showDot = date && hasNotification(date);
    return (
      <div className="custom-day-cell">
        <span>{day}</span>
        {showDot && <span className="notification-dot" />}
      </div>
    );
  };

  return (
    <DatePicker
        selected={startDate}
        onChange={(date) => setStartDate(date)}
        renderDayContents={renderDay}
        inline
    />
  );
}
