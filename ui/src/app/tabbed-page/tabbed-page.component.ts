import {
    Component,
    OnInit,
    OnDestroy,
    Input,
    Output,
    TemplateRef,
    QueryList,
    ContentChildren,
    AfterContentInit,
    forwardRef,
    Inject,
    EventEmitter,
} from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'

import { Subscription } from 'rxjs'

import { PrimeTemplate } from 'primeng/api'
import { MenuItem } from 'primeng/api'

@Component({
    selector: 'app-tabbed-page-tab',
    template: `<div [hidden]="!active">
        <ng-container *ngIf="visible && active">
            <ng-content></ng-content>
        </ng-container>
        <div></div>
    </div>`,
})
export class TabbedPageTabComponent {
    @Input() label: string = ''

    _visible: boolean = true
    active = false

    page: TabbedPageComponent

    constructor(@Inject(forwardRef(() => TabbedPageComponent)) page) {
        this.page = page as TabbedPageComponent
    }

    @Input() set visible(val) {
        this._visible = val
        this.page.checkTabsVisibility()
    }

    get visible() {
        return this._visible
    }
}

@Component({
    selector: 'app-tabbed-page',
    templateUrl: './tabbed-page.component.html',
    styleUrls: ['./tabbed-page.component.sass'],
})
export class TabbedPageComponent
    implements OnInit, OnDestroy, AfterContentInit
{
    _baseLinkUrl: string = ''

    @Output() tabChanged: EventEmitter<any> = new EventEmitter()

    @ContentChildren(PrimeTemplate) templates: QueryList<any>
    headerTemplate: TemplateRef<any>

    @ContentChildren(TabbedPageTabComponent)
    pageTabs: QueryList<TabbedPageTabComponent>
    tabs: TabbedPageTabComponent[]

    tabMenuItems: MenuItem[] = []
    activeTab: MenuItem
    activeTabIdx = 0

    private subs: Subscription = new Subscription()

    constructor(private route: ActivatedRoute, private router: Router) {}

    prepareMenuItemRouterLink(label) {
        let suffix = label.toLowerCase()
        suffix = suffix.replace(/ /g, '-')
        suffix = suffix.replace(/&/g, 'and')
        return this._baseLinkUrl + '/' + suffix
    }

    @Input() set baseLinkUrl(url) {
        this._baseLinkUrl = url

        for (let tmi of this.tabMenuItems) {
            tmi.routerLink = this.prepareMenuItemRouterLink(tmi.label)
        }
    }

    checkTabsVisibility() {
        let changed = false
        for (let idx = 0; idx < this.tabMenuItems.length; idx++) {
            if (this.tabMenuItems[idx].visible !== this.tabs[idx].visible) {
                changed = true
            }
        }
        if (changed) {
            this.initTabs()
        }
    }

    ngAfterContentInit() {
        this.templates.forEach((item) => {
            switch (item.getType()) {
                case 'header':
                    this.headerTemplate = item.template
                    break
            }
        })

        this.initTabs()

        this.subs.add(
            this.pageTabs.changes.subscribe((_) => {
                this.initTabs()
            })
        )
    }

    navigateToFirstTab() {
        if (this.tabMenuItems.length > 0) {
            const link = this.tabMenuItems[0].routerLink
            this.router.navigate([link], {
                replaceUrl: true,
            })
        }
    }

    initTabs() {
        this.tabs = this.pageTabs.toArray()

        this.tabMenuItems = []
        for (const t of this.tabs) {
            this.tabMenuItems.push({
                label: t.label,
                routerLink: this.prepareMenuItemRouterLink(t.label),
                visible: t.visible,
            })
        }

        if (this.tabMenuItems.length > 0) {
            let tab = this.route.snapshot.paramMap.get('tab')
            if (!tab) {
                // if no tab indicated then navigate to the first tab
                this.navigateToFirstTab()
                return
            }
            this.switchToTab(tab)
        } else {
            this.activeTab = null
        }
    }

    switchToTab(tabName) {
        for (let idx = 0; idx < this.tabMenuItems.length; idx++) {
            if (this.tabMenuItems[idx].routerLink.endsWith('/' + tabName)) {
                this.activeTab = this.tabMenuItems[idx]
                this.activeTabIdx = idx
                this.tabs[idx].active = true
            } else {
                this.tabs[idx].active = false
            }
        }
        this.tabChanged.emit(tabName)
    }

    ngOnInit(): void {
        this.subs.add(
            this.route.paramMap.subscribe((params) => {
                let tab = params.get('tab')

                if (!tab) {
                    // if no tab indicated then navigate to the first tab
                    this.navigateToFirstTab()
                    return
                }

                this.switchToTab(tab)
            })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }
}
