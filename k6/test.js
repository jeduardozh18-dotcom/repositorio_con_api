import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 25,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get('http://host.docker.internal:9001/');
  
  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
