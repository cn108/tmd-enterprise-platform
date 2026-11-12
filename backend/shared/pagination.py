"""One pagination contract for every list endpoint.

The portal must not download a whole table and filter it in the browser, so
lists are page-number paginated with a bounded page size. The response shape is
DRF's standard ``count/next/previous/results``; report endpoints that compute
rows in Python return ``rows`` plus the same ``count`` field.
"""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        # The v2 master-data contract uses `pageSize`; existing screens use
        # `page_size`. Both are bounded by max_page_size.
        camel_size = request.query_params.get("pageSize")
        if camel_size:
            try:
                return min(max(int(camel_size), 1), self.max_page_size)
            except ValueError:
                pass
        size = super().get_page_size(request)
        return size or self.page_size
