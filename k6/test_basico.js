import http from "k6/http";
import { check } from "k6";

const API_BASE = (__ENV.API_BASE || "http://backend:8000").replace(/\/+$/, "");

export const options = {
  stages: [
    { duration: "30s", target: 1 },
    { duration: "1m", target: 5 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const response = http.get(`${API_BASE}/`);
  check(response, {
    "API responds with HTTP 200": (res) => res.status === 200,
  });
}
