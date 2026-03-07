from django.urls import path
from . import views

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('user/', views.UserInfoView.as_view(), name='user_info'),

    # ── Farmer management (company agent only) ────────────────────────────
    path('farmers/', views.CreateFarmerView.as_view(), name='farmers'),
    path('farmers/list/', views.ListFarmersView.as_view(), name='list_farmers'),

    # ── Cow registration & listing ────────────────────────────────────────
    path('register/', views.RegisterCowView.as_view(), name='register'),
    path('profiles/', views.ListProfilesView.as_view(), name='list_profiles'),
    path('my-cows/', views.MyCowsView.as_view(), name='my_cows'),

    # ── ML helpers ────────────────────────────────────────────────────────
    path('classify/', views.ClassifyCowView.as_view(), name='classify_cow'),
    path('training-status/<int:training_id>/', views.TrainingStatusView.as_view(), name='training_status'),

    # ── Insurance claims ──────────────────────────────────────────────────
    path('claims/', views.ClaimsListCreateView.as_view(), name='claims_list_create'),
    path('claims/<int:claim_id>/assign/', views.ClaimAssignView.as_view(), name='claim_assign'),
    path('claims/<int:claim_id>/verify/', views.ClaimVerifyView.as_view(), name='claim_verify'),
    path('claims/<int:claim_id>/approve/', views.ClaimApproveView.as_view(), name='claim_approve'),

    # ── Admin read endpoints ──────────────────────────────────────────────
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin/company-agents/', views.AdminCompanyAgentsView.as_view(), name='admin_company_agents'),
    path('admin/farmers/', views.AdminFarmersView.as_view(), name='admin_farmers'),
    path('admin/claims/', views.AdminClaimsView.as_view(), name='admin_claims'),
]
