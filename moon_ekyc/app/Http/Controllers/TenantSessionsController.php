<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class TenantSessionsController extends Controller
{
    public function index(Request $request): Response
    {
        return Inertia::render('Tenant/Sessions', [
            'summary' => [
                'totalSessions' => 0,
                'pendingReviews' => 0,
            ],
            'filters' => [
                'search' => '',
                'reviewStatus' => '',
            ],
            'sessions' => [],
        ]);
    }
}
