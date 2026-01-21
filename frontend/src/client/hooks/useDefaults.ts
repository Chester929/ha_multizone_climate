import { useState, useEffect } from 'react';

interface ZoneDefaults {
  opening_offset: number;
  closing_offset: number;
  target_change_threshold: number;
  priority: number;
}

interface GlobalDefaults {
  main_target_all_zones_satisfied: number;
  use_average_mode: boolean;
  slider_position: number;
  min_valves_open: number;
  main_min_temp: number;
  main_max_temp: number;
  main_change_threshold: number;
  valve_actuation_delay: number;
  coordinator_interval: number;
  satisfaction_eps: number;
}

interface Defaults {
  zone: ZoneDefaults;
  global: GlobalDefaults;
}

export function useDefaults() {
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDefaults = async () => {
      try {
        const response = await fetch('/api/defaults');
        if (response.ok) {
          const data = await response.json();
          setDefaults(data);
        } else {
          setError('Failed to fetch defaults');
        }
      } catch (err) {
        setError('Error fetching defaults');
        console.error('Error fetching defaults:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchDefaults();
  }, []);

  return { defaults, loading, error };
}
