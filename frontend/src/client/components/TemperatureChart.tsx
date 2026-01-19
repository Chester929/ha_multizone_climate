import React, { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { HistoricalDataPoint } from '../types';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

interface TemperatureChartProps {
  zoneId: string;
  zoneName: string;
  hours?: number;
}

export function TemperatureChart({ zoneId, zoneName, hours = 24 }: TemperatureChartProps) {
  const [data, setData] = useState<HistoricalDataPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(`/api/history/zones/${zoneId}?hours=${hours}`);
        const historyData = await response.json();
        setData(historyData.reverse()); // Reverse to show oldest first
        setLoading(false);
      } catch (error) {
        console.error('Error fetching historical data:', error);
        setLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute

    return () => clearInterval(interval);
  }, [zoneId, hours]);

  if (loading) {
    return <div className="loading">Loading chart data...</div>;
  }

  if (data.length === 0) {
    return <div className="no-data">No historical data available</div>;
  }

  const chartData = {
    labels: data.map(d => {
      const date = new Date(d.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }),
    datasets: [
      {
        label: 'Current Temperature',
        data: data.map(d => {
          const temp = d.current_temperature ? parseFloat(d.current_temperature) : null;
          return temp !== null && !isNaN(temp) ? temp : null;
        }),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
        tension: 0.4,
        spanGaps: true,
      },
      {
        label: 'Target Temperature',
        data: data.map(d => {
          const temp = d.target_temperature ? parseFloat(d.target_temperature) : null;
          return temp !== null && !isNaN(temp) ? temp : null;
        }),
        borderColor: 'rgb(54, 162, 235)',
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        tension: 0.4,
        spanGaps: true,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: `${zoneName} - Temperature History (${hours}h)`,
      },
    },
    scales: {
      y: {
        title: {
          display: true,
          text: 'Temperature (°C)',
        },
      },
      x: {
        title: {
          display: true,
          text: 'Time',
        },
      },
    },
  };

  return (
    <div style={{ height: '300px', marginTop: '20px' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
