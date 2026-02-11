from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import requests


logger = logging.getLogger(__name__)


class AvalaraClient:
    """
    Client for Avalara CertCapture / Exemption Certificate Management API.

    Auth: Basic authentication (username:password)
    Base URL: https://rest.avatax.com/api/v2
    """

    def __init__(self, username: str, password: str, company_id: int):
        self.base_url = "https://rest.avatax.com/api/v2"
        self.auth = (username, password)
        self.company_id = company_id

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, auth=self.auth, timeout=30, **kwargs)
        if response.status_code >= 400:
            try:
                message = response.json()
            except ValueError:
                message = response.text
            raise RuntimeError(f"Avalara API error {response.status_code}: {message}")
        return response

    def list_certificates(
        self,
        top: int = 50,
        skip: int = 0,
        filter_str: Optional[str] = None,
    ) -> dict:
        """
        List certificates for the company.

        GET /api/v2/companies/{companyId}/certificates

        Params:
        - $top: number of results (max 1000)
        - $skip: pagination offset
        - $filter: OData filter (e.g., "status eq 'Active'")

        Returns: API response dict with "value" list of certificates
        """
        params: dict[str, str | int] = {"$top": min(top, 1000), "$skip": max(skip, 0)}
        if filter_str:
            params["$filter"] = filter_str

        response = self._request("GET", f"/companies/{self.company_id}/certificates", params=params)
        return response.json()

    def get_certificate(self, cert_id: int) -> dict:
        """Get a single certificate with full details."""
        response = self._request("GET", f"/companies/{self.company_id}/certificates/{cert_id}")
        return response.json()

    def download_certificate_pdf(self, cert_id: int, output_path: str) -> str:
        """
        Download the certificate PDF/image attachment.

        GET /api/v2/companies/{companyId}/certificates/{id}/attachment

        Saves to output_path. Returns the path.
        """
        response = self._request("GET", f"/companies/{self.company_id}/certificates/{cert_id}/attachment")
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.content)
        return str(out)

    def get_customer_certificates(self, customer_code: str) -> list[dict]:
        """
        List all certificates for a specific customer.

        GET /api/v2/companies/{companyId}/certificates
          ?$filter=customerCode eq '{customer_code}'
        """
        payload = self.list_certificates(top=1000, filter_str=f"customerCode eq '{customer_code}'")
        return payload.get("value", [])

    def update_certificate_status(self, cert_id: int, status: str) -> dict:
        """
        Update a certificate's status in Avalara.

        PUT /api/v2/companies/{companyId}/certificates/{id}

        Valid statuses: "Active", "Inactive", "Expired", "Revoked"
        """
        valid_statuses = {"Active", "Inactive", "Expired", "Revoked"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {sorted(valid_statuses)}")

        existing = self.get_certificate(cert_id)
        existing["status"] = status
        response = self._request(
            "PUT",
            f"/companies/{self.company_id}/certificates/{cert_id}",
            json=existing,
        )
        return response.json()

    def list_all_certificates(self, batch_size: int = 100) -> list[dict]:
        """
        Paginate through ALL certificates for the company.

        Loops through list_certificates() with $skip until all certs retrieved.
        Returns complete list.

        Handle rate limiting: if 429 response, wait and retry.
        Log progress: "Retrieved {n} of {total} certificates..."
        """
        all_certs: list[dict] = []
        skip = 0
        capped_batch = min(max(batch_size, 1), 1000)
        total_count: Optional[int] = None

        while True:
            try:
                payload = self.list_certificates(top=capped_batch, skip=skip)
            except RuntimeError as exc:
                if "429" in str(exc):
                    logger.warning("Avalara rate limit reached, retrying in 2 seconds...")
                    time.sleep(2)
                    continue
                raise

            page = payload.get("value", [])
            if total_count is None:
                total_count = payload.get("count") or payload.get("totalCount")

            if not page:
                break

            all_certs.extend(page)
            if total_count:
                logger.info("Retrieved %s of %s certificates...", len(all_certs), total_count)
            else:
                logger.info("Retrieved %s certificates...", len(all_certs))

            if len(page) < capped_batch:
                break
            skip += capped_batch

        return all_certs
