<?php

namespace App\Http\Controllers;

use Inertia\Inertia;
use Inertia\Response;

class TenantReviewController extends Controller
{
    public function index(): Response
    {
        return Inertia::render('Tenant/Review', [
            'queue' => [],
        ]);
    }
}
