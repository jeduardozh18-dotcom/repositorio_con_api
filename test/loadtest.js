import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
    vus: 10,            // usuarios virtuales
    duration: '20s',    // duración de la prueba
    thresholds: {
        http_req_duration: ['p(95)<500'],  // 95% de peticiones < 500 ms
    }
};

export default function () {
    const res = http.get('http://localhost:9000/docs');

    check(res, {
        'status es 200': (r) => r.status === 200,
    });

    sleep(1);
}
