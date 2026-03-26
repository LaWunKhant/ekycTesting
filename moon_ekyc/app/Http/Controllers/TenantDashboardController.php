<?php

namespace App\Http\Controllers;

use App\Http\Requests\TenantCreateCustomerRequest;
use App\Models\Customer;
use App\Models\VerificationLink;
use Carbon\Carbon;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;
use Throwable;
use Inertia\Inertia;
use Inertia\Response;

class TenantDashboardController extends Controller
{
    public function show(Request $request): Response
    {
        $user = $request->user();
        $tenant = $user?->tenant;
        $latestLink = null;

        if ($tenant) {
            $latestLink = VerificationLink::query()
                ->where('tenant_uuid', $tenant->uuid)
                ->latest('created_at')
                ->first();
        }

        return Inertia::render('Dashboard', [
            'workspace' => [
                'name' => 'MoonKYC Tenant Workspace',
                'subtitle' => 'Your customers, verification sessions, and review queue',
                'tenantName' => $tenant?->name ?? $user?->name ?? 'Tenant Workspace',
            ],
            'stats' => [
                [
                    'label' => 'Total Sessions',
                    'value' => '0',
                    'caption' => 'Session totals will appear here after tenant session tables are wired.',
                    'tone' => 'cyan',
                ],
                [
                    'label' => 'Pending Reviews',
                    'value' => '0',
                    'caption' => 'Manual review queue count for this tenant.',
                    'tone' => 'amber',
                ],
            ],
            'actions' => [
                [
                    'label' => 'Customer Sessions',
                    'href' => '/sessions',
                    'caption' => 'Search customers, review status, and verification progress.',
                ],
                [
                    'label' => 'Team Management',
                    'href' => '/team',
                    'caption' => 'Invite tenant members and manage roles.',
                ],
                [
                    'label' => 'Review Queue',
                    'href' => '/review',
                    'caption' => 'Open the final review queue for manual approval.',
                ],
            ],
            'quickStart' => [
                'title' => 'Create Customer + Send Verification',
                'description' => 'This panel mirrors the Django tenant dashboard flow. Wire the form to your Laravel customer/session backend next.',
                'fields' => ['Full Name', 'Email', 'Phone', 'External Ref'],
            ],
            'latestLink' => [
                'url' => $latestLink ? $this->verificationLinkUrl($latestLink->token) : null,
                'status' => $latestLink ? 'Latest verification link ready to share.' : 'No verification link generated yet.',
            ],
            'status' => $request->session()->get('status'),
            'mailError' => $request->session()->get('mail_error'),
        ]);
    }

    public function store(TenantCreateCustomerRequest $request): RedirectResponse
    {
        $user = $request->user();
        $tenant = $user?->tenant;

        abort_unless($tenant !== null, 403, 'No tenant assigned.');

        $validated = $request->validated();

        $customer = Customer::create([
            'tenant_uuid' => $tenant->uuid,
            'full_name' => $validated['full_name'],
            'email' => $validated['email'] ?: null,
            'phone' => $validated['phone'] ?: null,
            'external_ref' => $validated['external_ref'] ?: null,
            'status' => 'active',
            'created_at' => now(),
        ]);

        $verificationLink = VerificationLink::create([
            'token' => str_replace('-', '', (string) Str::uuid()),
            'tenant_uuid' => $tenant->uuid,
            'customer_id' => $customer->id,
            'created_at' => now(),
            'expires_at' => Carbon::now()->addDays(2),
        ]);

        if ($customer->email) {
            $mailError = $this->sendVerificationEmail($customer->full_name, $customer->email, $verificationLink->token);

            if ($mailError !== null) {
                return redirect()
                    ->route('dashboard')
                    ->with('status', 'Verification link generated successfully.')
                    ->with('mail_error', $mailError);
            }
        }

        return redirect()
            ->route('dashboard')
            ->with('status', 'Verification link generated successfully.');
    }

    private function verificationLinkUrl(string $token): string
    {
        $publicBaseUrl = rtrim((string) env('PUBLIC_BASE_URL', ''), '/');
        $urlToken = $this->formatTokenForPublicUrl($token);

        if ($publicBaseUrl !== '') {
            return "{$publicBaseUrl}/verify/start/{$urlToken}/";
        }

        return rtrim(config('app.url'), '/')."/verify/start/{$urlToken}/";
    }

    private function formatTokenForPublicUrl(string $token): string
    {
        if (Str::isUuid($token)) {
            return $token;
        }

        $normalized = strtolower(trim($token));

        if (preg_match('/^[a-f0-9]{32}$/', $normalized) !== 1) {
            return $token;
        }

        return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split($normalized, 4));
    }

    private function sendVerificationEmail(string $fullName, string $email, string $token): ?string
    {
        if (! $this->hasUsableSmtpCredentials()) {
            return 'The verification link was created, but the email was not sent because the Mailtrap SMTP username or password is missing or invalid.';
        }

        $linkUrl = $this->verificationLinkUrl($token);

        try {
            Mail::raw(
                "Hello {$fullName},\n\n"
                ."Please complete your verification using this link:\n{$linkUrl}\n\n"
                .'This link expires in 48 hours.',
                function ($message) use ($email) {
                    $message
                        ->to($email)
                        ->subject('Your KYC Verification');
                }
            );
        } catch (Throwable $exception) {
            report($exception);

            return 'The verification link was created, but the email could not be sent. Please check your Mailtrap SMTP credentials.';
        }

        return null;
    }

    private function hasUsableSmtpCredentials(): bool
    {
        if (config('mail.default') !== 'smtp') {
            return true;
        }

        $username = (string) config('mail.mailers.smtp.username');
        $password = (string) config('mail.mailers.smtp.password');

        if ($username === '' || $password === '') {
            return false;
        }

        return ! str_contains($password, '*');
    }
}
