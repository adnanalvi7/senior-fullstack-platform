from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.properties.views import PropertyViewSet, BudgetListView

router = DefaultRouter()
router.register(r'', PropertyViewSet, basename='property')

urlpatterns = [
    path('budgets/', BudgetListView.as_view(), name='budget_list'),
    path('', include(router.urls)),
]
